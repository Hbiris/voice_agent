import logging
import time
from dataclasses import dataclass, field

from livekit import agents
from livekit.agents import AgentSession, Agent, JobContext, RoomInputOptions
from livekit.agents.llm import ChatMessage
from livekit.agents.metrics import EOUMetrics, RealtimeModelMetrics
from livekit.agents.voice.events import (
    CloseEvent,
    ConversationItemAddedEvent,
    MetricsCollectedEvent,
    UserInputTranscribedEvent,
)

from src.agent.prompt import CASCADED_GREETING, GREETING_INSTRUCTION, VISITOR_SYSTEM_PROMPT
from src.tools.visitor import submit_visitor_registration
from src.voice.factory import build_voice_kwargs

logger = logging.getLogger(__name__)


@dataclass
class CallTimer:
    t_connected: float = field(default_factory=time.perf_counter)
    t_greeting: float = 0.0
    t_tool_submitted: float = 0.0   # set by submit_visitor_registration
    t_wechat_sent: float = 0.0      # set by submit_visitor_registration after push_wechat
    ai_ttfts: list[float] = field(default_factory=list)  # RealtimeModelMetrics.ttft per turn
    transcripts: list[str] = field(default_factory=list)  # final caller transcripts for anti-fabrication check


def _handle_user_transcript(timer: CallTimer, ev: UserInputTranscribedEvent) -> None:
    if ev.is_final:
        timer.transcripts.append(ev.transcript)
        logger.info("[caller said] %s", ev.transcript)


def _log_agent_transcript(ev: ConversationItemAddedEvent) -> None:
    item = ev.item
    if isinstance(item, ChatMessage) and item.role == "assistant":
        text = item.text_content
        if text:
            logger.info("[agent said] %s", text)


def _on_metrics(timer: CallTimer, ev: MetricsCollectedEvent) -> None:
    m = ev.metrics
    if isinstance(m, RealtimeModelMetrics) and m.ttft >= 0:
        turn = len(timer.ai_ttfts) + 1
        timer.ai_ttfts.append(m.ttft)
        logger.info(
            "[latency] turn=%d  AI ttft=%.2fs  (tokens in=%d out=%d)",
            turn, m.ttft, m.input_tokens, m.output_tokens,
        )
    elif isinstance(m, EOUMetrics) and m.end_of_utterance_delay > 0:
        logger.info(
            "[latency] EOU delay=%.2fs  transcription_delay=%.2fs",
            m.end_of_utterance_delay, m.transcription_delay,
        )


def _on_close(timer: CallTimer, _ev: CloseEvent) -> None:
    if not timer.ai_ttfts:
        return
    cold_start = (timer.t_greeting - timer.t_connected) if timer.t_greeting > 0 else 0.0
    t_end_ref = timer.t_wechat_sent if timer.t_wechat_sent > 0 else (
        timer.t_tool_submitted if timer.t_tool_submitted > 0 else time.perf_counter()
    )
    budget = (t_end_ref - timer.t_greeting) if timer.t_greeting > 0 else 0.0
    total_ai = sum(timer.ai_ttfts)
    avg_ai = total_ai / len(timer.ai_ttfts)
    ratio = (total_ai / budget * 100) if budget > 0 else 0.0
    logger.info(
        "[summary] turns=%d | ai_total=%.2fs | ai_avg=%.2fs"
        " | cold_start=%.2fs(不计入预算) | budget=%.2fs(25s指标) | ai_ratio=%.1f%%",
        len(timer.ai_ttfts), total_ai, avg_ai, cold_start, budget, ratio,
    )


async def entrypoint(ctx: JobContext) -> None:
    logger.info("incoming call → room=%s", ctx.room.name)

    # 建表（幂等），在连接 room 前完成，不占 25 秒通话预算
    from src.data.database import init_db
    await init_db()

    await ctx.connect()
    timer = CallTimer()  # t_connected 记录在此刻
    logger.info("[timing] call connected")

    voice_kwargs = build_voice_kwargs()
    session = AgentSession(userdata=timer, **voice_kwargs)

    session.on("user_input_transcribed", lambda ev: _handle_user_transcript(timer, ev))
    session.on("conversation_item_added", _log_agent_transcript)
    session.on("metrics_collected", lambda ev: _on_metrics(timer, ev))
    session.on("close", lambda ev: _on_close(timer, ev))

    agent = Agent(
        instructions=VISITOR_SYSTEM_PROMPT,
        tools=[submit_visitor_registration],
    )

    await session.start(
        agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )

    # 接通后主动开口，一句话问 3 项（车牌 + 单位 + 事由），让对话自然展开
    # cascaded 模式：session.say() 固定文本直接走 CosyVoice TTS，跳过 LLM round-trip
    # realtime 模式：generate_reply(instructions=...) 让 Realtime 模型自由生成问候
    from src.config.settings import get_settings
    if get_settings().demo_voice_mode == "cascaded":
        await session.say(CASCADED_GREETING, add_to_chat_ctx=True)
    else:
        await session.generate_reply(instructions=GREETING_INSTRUCTION)
    timer.t_greeting = time.perf_counter()
    logger.info(
        "[timing] greeting sent [%.0fms after connect]",
        (timer.t_greeting - timer.t_connected) * 1000,
    )

    logger.info("session live, waiting for caller input")


def main() -> None:
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            # agent_name 必须与 dispatch rule 中的 RoomAgentDispatch.agent_name 完全一致
            agent_name="visitor-agent",
        )
    )


if __name__ == "__main__":
    main()
