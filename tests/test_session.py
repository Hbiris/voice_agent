"""session 组装测试：验证 build_agent_session 正确使用 voice kwargs 和 prompt。"""
import pytest
from unittest.mock import patch, MagicMock


class TestPrompt:
    def test_greeting_not_empty(self):
        from src.agent.prompt import GREETING_INSTRUCTION
        assert len(GREETING_INSTRUCTION) > 10
        assert "中文" in GREETING_INSTRUCTION or "访客" in GREETING_INSTRUCTION

    def test_system_prompt_contains_required_fields(self):
        from src.agent.prompt import VISITOR_SYSTEM_PROMPT
        for field in ["车牌号", "来访单位", "手机号", "来访事由"]:
            assert field in VISITOR_SYSTEM_PROMPT, f"Missing field in prompt: {field}"

    def test_system_prompt_not_empty(self):
        from src.agent.prompt import VISITOR_SYSTEM_PROMPT
        assert len(VISITOR_SYSTEM_PROMPT) > 50


class TestBuildAgentSession:
    def test_returns_session_and_agent(self):
        """build_agent_session 应返回 (AgentSession, Agent) 元组。"""
        mock_session = MagicMock()
        mock_agent = MagicMock()
        mock_llm = MagicMock()

        # 在 session 模块的命名空间内 patch，避免 reload 覆盖问题
        with patch("src.agent.session.build_voice_kwargs", return_value={"llm": mock_llm}):
            with patch("src.agent.session.AgentSession", return_value=mock_session) as MockSession:
                with patch("src.agent.session.Agent", return_value=mock_agent) as MockAgent:
                    from src.agent.session import build_agent_session
                    result = build_agent_session()

                    assert result == (mock_session, mock_agent)
                    MockSession.assert_called_once_with(llm=mock_llm)
                    MockAgent.assert_called_once()
                    assert "instructions" in MockAgent.call_args.kwargs
