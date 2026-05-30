"""
session 组装辅助函数（可选）。
worker.py 直接组装，本模块供测试和未来多 session 场景复用。
"""
import logging
from livekit.agents import AgentSession, Agent

from src.agent.prompt import VISITOR_SYSTEM_PROMPT
from src.voice.factory import build_voice_kwargs

logger = logging.getLogger(__name__)


def build_agent_session() -> tuple[AgentSession, Agent]:
    """从当前 profile 构建 AgentSession 和 Agent，供 entrypoint 使用。"""
    voice_kwargs = build_voice_kwargs()
    logger.debug("AgentSession voice kwargs: %s", list(voice_kwargs.keys()))
    session = AgentSession(**voice_kwargs)
    agent = Agent(instructions=VISITOR_SYSTEM_PROMPT)
    return session, agent
