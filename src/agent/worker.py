import logging

from livekit import agents
from livekit.agents import AgentSession, Agent, JobContext, RoomInputOptions

from src.agent.prompt import GREETING_INSTRUCTION, VISITOR_SYSTEM_PROMPT
from src.tools.visitor import submit_visitor_registration
from src.voice.factory import build_voice_kwargs

logger = logging.getLogger(__name__)


async def entrypoint(ctx: JobContext) -> None:
    logger.info("incoming call → room=%s", ctx.room.name)

    # 建表（幂等），在连接 room 前完成，不占 25 秒通话预算
    from src.data.database import init_db
    await init_db()

    await ctx.connect()

    voice_kwargs = build_voice_kwargs()
    session = AgentSession(**voice_kwargs)
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
