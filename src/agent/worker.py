import logging

from livekit import agents
from livekit.agents import AgentSession, Agent, JobContext, RoomInputOptions

from src.agent.prompt import GREETING, VISITOR_SYSTEM_PROMPT
from src.voice.factory import build_voice_kwargs

logger = logging.getLogger(__name__)


async def entrypoint(ctx: JobContext) -> None:
    logger.info("incoming call → room=%s", ctx.room.name)

    await ctx.connect()

    voice_kwargs = build_voice_kwargs()
    session = AgentSession(**voice_kwargs)
    agent = Agent(instructions=VISITOR_SYSTEM_PROMPT)

    await session.start(
        agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(),
    )

    # 主动问候，让访客感知到 Agent 已接通
    await session.generate_reply(
    instructions="用中文向访客问好，说明这里是园区访客登记，并询问车牌号和来访哪家公司"
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
