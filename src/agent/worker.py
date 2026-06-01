import logging

from livekit import agents
from livekit.agents import AgentSession, Agent, JobContext, RoomInputOptions
from livekit.agents.llm import ChatMessage
from livekit.agents.voice.events import ConversationItemAddedEvent, UserInputTranscribedEvent

from src.agent.prompt import GREETING_INSTRUCTION, VISITOR_SYSTEM_PROMPT
from src.tools.visitor import submit_visitor_registration
from src.voice.factory import build_voice_kwargs

logger = logging.getLogger(__name__)


def _log_user_transcript(ev: UserInputTranscribedEvent) -> None:
    if ev.is_final:
        logger.info("[caller said] %s", ev.transcript)


def _log_agent_transcript(ev: ConversationItemAddedEvent) -> None:
    item = ev.item
    if isinstance(item, ChatMessage) and item.role == "assistant":
        text = item.text_content
        if text:
            logger.info("[agent said] %s", text)


async def entrypoint(ctx: JobContext) -> None:
    logger.info("incoming call → room=%s", ctx.room.name)

    # 建表（幂等），在连接 room 前完成，不占 25 秒通话预算
    from src.data.database import init_db
    await init_db()

    await ctx.connect()

    voice_kwargs = build_voice_kwargs()
    session = AgentSession(**voice_kwargs)

    # 把来电者的每条最终识别结果打到日志，用于验证模型收到的是真实输入而非编造值
    session.on("user_input_transcribed", _log_user_transcript)
    # 把 agent 每轮说出的话打到日志，用于核查复述内容是否与来电者输入一致
    session.on("conversation_item_added", _log_agent_transcript)

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
    await session.generate_reply(instructions=GREETING_INSTRUCTION)

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
