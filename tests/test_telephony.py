"""telephony 配置校验测试：dispatch rule 结构合法性（不发真实 API 请求）。"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestInboundConfig:
    def test_twilio_ips_not_empty(self):
        """Twilio IP 白名单应有值（配置未被清空）。"""
        from src.telephony.inbound import TWILIO_SIP_IPS
        assert len(TWILIO_SIP_IPS) > 0
        for ip in TWILIO_SIP_IPS:
            assert "/" in ip, f"Expected CIDR notation: {ip}"

    def test_aliyun_ips_placeholder(self):
        """阿里云 IP 列表应为空列表（待落地时填入，不应 None）。"""
        from src.telephony.inbound import ALIYUN_SIP_IPS
        assert isinstance(ALIYUN_SIP_IPS, list)

    def test_room_prefix_in_settings(self):
        from src.config.settings import Settings
        with patch.dict("os.environ", {"VOICE_PROFILE": "demo"}):
            s = Settings()
            assert s.sip_room_prefix == "call-"
            assert s.agent_name == "visitor-agent"

    def test_agent_name_consistency(self):
        """worker 中 agent_name 必须与 settings.agent_name 默认值一致。"""
        from src.config.settings import Settings
        s = Settings()
        # 与 worker.py 中 WorkerOptions(agent_name="visitor-agent") 一致
        assert s.agent_name == "visitor-agent"


class TestCreateInboundTrunk:
    @pytest.mark.asyncio
    async def test_create_trunk_calls_api(self):
        """create_inbound_trunk 应调用 lkapi.sip.create_sip_inbound_trunk。"""
        from src.telephony.inbound import create_inbound_trunk

        mock_response = MagicMock()
        mock_response.sip_trunk_id = "TR_test123"

        mock_lkapi = MagicMock()
        mock_lkapi.sip.create_sip_inbound_trunk = AsyncMock(return_value=mock_response)

        with patch("src.telephony.inbound.SIPInboundTrunkInfo"):
            with patch("src.telephony.inbound.CreateSIPInboundTrunkRequest"):
                result = await create_inbound_trunk(
                    mock_lkapi,
                    phone_numbers=["+18005551234"],
                )
        mock_lkapi.sip.create_sip_inbound_trunk.assert_called_once()
        assert result == mock_response


class TestCreateDispatchRule:
    @pytest.mark.asyncio
    async def test_create_rule_uses_agent_name(self):
        """create_dispatch_rule 应将 agent_name 传入 RoomAgentDispatch。"""
        from src.telephony.inbound import create_dispatch_rule

        mock_response = MagicMock()
        mock_response.sip_dispatch_rule_id = "DR_test456"

        mock_lkapi = MagicMock()
        mock_lkapi.sip.create_sip_dispatch_rule = AsyncMock(return_value=mock_response)

        captured_rule = {}

        def capture_request(req):
            captured_rule["req"] = req
            return mock_response

        mock_lkapi.sip.create_sip_dispatch_rule = AsyncMock(side_effect=capture_request)

        with patch("src.telephony.inbound.SIPDispatchRuleInfo") as MockRuleInfo, \
             patch("src.telephony.inbound.SIPDispatchRule"), \
             patch("src.telephony.inbound.SIPDispatchRuleIndividual"), \
             patch("src.telephony.inbound.RoomConfiguration"), \
             patch("src.telephony.inbound.RoomAgentDispatch") as MockAgentDispatch, \
             patch("src.telephony.inbound.CreateSIPDispatchRuleRequest"):

            await create_dispatch_rule(
                mock_lkapi,
                trunk_id="TR_test123",
                agent_name="visitor-agent",
                room_prefix="call-",
            )

            # RoomAgentDispatch 应以 agent_name="visitor-agent" 构造
            MockAgentDispatch.assert_called_once_with(
                agent_name="visitor-agent",
                metadata='{"source":"sip"}',
            )
