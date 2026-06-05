import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime

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

# room name 里主叫号码部分：下划线前的 +86XXXXXXXXXXX 或 XXXXXXXXXXX
_CALLER_PART_RE = re.compile(r"(\+?\d+)_")


@dataclass
class CallTimer:
    t_connected: float = field(default_factory=time.perf_counter)
    t_greeting: float = 0.0
    t_tool_submitted: float = 0.0    # set by submit_visitor_registration
    t_wechat_sent: float = 0.0       # set by submit_visitor_registration after push_wechat
    ai_ttfts: list[float] = field(default_factory=list)
    transcripts: list[str] = field(default_factory=list)
    caller_id: str | None = None     # normalized 11-digit caller number


def _parse_caller_id(room_name: str) -> str | None:
    """从 room name 解析并规范化主叫号码为 11 位。

    格式示例：+8618983280231_abc123 / call-+8618983280231_abc / 18983280231_xyz
    规则：取下划线前的数字串；若为 13 位且以 86 开头则去掉前缀；11 位且以 1 开头则有效。
    """
    m = _CALLER_PART_RE.search(room_name)
    if not m:
        return None
    digits = re.sub(r"\D", "", m.group(1))
    if len(digits) == 13 and digits.startswith("86"):
        digits = digits[2:]
    if len(digits) == 11 and digits[0] == "1":
        return digits
    return None


def _friendly_date(dt: datetime) -> str:
    days_ago = (datetime.now().date() - dt.date()).days
    if days_ago == 0:
        return "今天早些时候"
    if days_ago == 1:
        return "昨天"
    return f"{dt.month}月{dt.day}日"


def _returning_visitor_context(last_visit) -> tuple[str, str, str]:
    """构建回访场景的三元素：(system_prompt_addition, cascaded_greeting, realtime_instruction)。"""
    date_str = _friendly_date(last_visit.arrived_at)
    p = last_visit.plate
    c = last_visit.company
    pu = last_visit.purpose
    ph = last_visit.phone

    prompt_addition = f"""

━━ 回访识别·老访客 ━━
来电者是回头客，上次（{date_str}）登记如下：
  车牌：{p}  单位：{c}  事由：{pu}  手机：{ph}

【第 1 轮（替换常规开场）】
一句话确认是否沿用上次信息。
参考：「您好，看着{date_str}您来过，今天还是开{p}来{c}{pu}吗？」

【来电者确认（"对"/"是"/"一样"/"嗯"/"没变"等）】
→ 立即调用 submit_visitor_registration，填入上次四项原值，reused_from_caller_history=True。
→ 无需追问任何字段，目标 ≤ 2 轮完成。

【来电者说有变化】
→ 只追问发生变化的字段，其余沿用上次值，reused_from_caller_history=False。
"""

    cascaded_greeting = (
        f"您好，看着{date_str}您来过，"
        f"今天还是开{p}来{c}{pu}吗？"
    )

    realtime_instruction = (
        f"用亲切口语问好，一句话确认来电者是否沿用上次（{date_str}）来访信息："
        f"车牌{p}、{c}、{pu}。"
        f"参考：「您好，看着{date_str}您来过，今天还是开{p}来{c}{pu}吗？」"
    )

    return prompt_addition, cascaded_greeting, realtime_instruction


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

    # ── 解析主叫号码，查询回访记录 ──────────────────────────────────────────────
    caller_id = _parse_caller_id(ctx.room.name)
    last_visit = None
    if caller_id:
        from src.data.query import get_last_visit_by_caller
        last_visit = await get_last_visit_by_caller(caller_id)
        if last_visit:
            logger.info(
                "[returning visitor] caller=%s last_id=%s arrived=%s",
                caller_id, last_visit.id, last_visit.arrived_at,
            )
        else:
            logger.info("[new visitor] caller=%s", caller_id)
    else:
        logger.info("[unknown caller] room=%s (no phone in room name)", ctx.room.name)

    timer = CallTimer(caller_id=caller_id)
    logger.info("[timing] call connected")

    # ── 构建指令和问候语（回访 vs 首访） ────────────────────────────────────────
    if last_visit:
        prompt_addition, greeting_cascaded, greeting_realtime = _returning_visitor_context(last_visit)
        instructions = VISITOR_SYSTEM_PROMPT + prompt_addition
    else:
        instructions = VISITOR_SYSTEM_PROMPT
        greeting_cascaded = CASCADED_GREETING
        greeting_realtime = GREETING_INSTRUCTION

    voice_kwargs = build_voice_kwargs()
    session = AgentSession(userdata=timer, **voice_kwargs)

    session.on("user_input_transcribed", lambda ev: _handle_user_transcript(timer, ev))
    session.on("conversation_item_added", _log_agent_transcript)
    session.on("metrics_collected", lambda ev: _on_metrics(timer, ev))
    session.on("close", lambda ev: _on_close(timer, ev))

    agent = Agent(
        instructions=instructions,
        tools=[submit_visitor_registration],
    )

    await session.start(
        agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )

    # ── 开口问候 ─────────────────────────────────────────────────────────────────
    from src.config.settings import get_settings
    if get_settings().demo_voice_mode == "cascaded":
        await session.say(greeting_cascaded, add_to_chat_ctx=True)
    else:
        await session.generate_reply(instructions=greeting_realtime)

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
            agent_name="visitor-agent",
        )
    )


if __name__ == "__main__":
    main()
