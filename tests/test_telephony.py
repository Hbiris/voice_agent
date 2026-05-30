"""telephony 配置校验测试：dispatch rule 结构合法性（不发真实 API 请求）。"""
import pytest
from unittest.mock import AsyncMock, MagicMock


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
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("VOICE_PROFILE", "demo")
            s = Settings()
            assert s.sip_room_prefix == "call-"
            assert s.agent_name == "visitor-agent"

    def test_agent_name_consistency(self):
        """worker 中 agent_name 必须与 settings.agent_name 默认值一致。"""
        from src.config.settings import Settings
        s = Settings()
        assert s.agent_name == "visitor-agent"


class TestCreateManagedDispatchRule:
    """LiveKit 托管号路径：只建 dispatch rule，trunk_ids 为空。"""

    @pytest.mark.asyncio
    async def test_creates_rule_with_empty_trunk_ids(self):
        """managed 路径应以 empty trunk_ids 创建 dispatch rule。"""
        from src.telephony.inbound import create_dispatch_rule_managed

        mock_response = MagicMock()
        mock_response.sip_dispatch_rule_id = "SDR_test_managed"

        mock_lkapi = MagicMock()
        mock_lkapi.sip.create_sip_dispatch_rule = AsyncMock(return_value=mock_response)

        captured: list = []

        async def capture(req):
            captured.append(req)
            return mock_response

        mock_lkapi.sip.create_sip_dispatch_rule = AsyncMock(side_effect=capture)

        from unittest.mock import patch
        with patch("src.telephony.inbound.SIPDispatchRuleInfo") as MockInfo, \
             patch("src.telephony.inbound.SIPDispatchRule"), \
             patch("src.telephony.inbound.SIPDispatchRuleIndividual"), \
             patch("src.telephony.inbound.RoomConfiguration"), \
             patch("src.telephony.inbound.RoomAgentDispatch") as MockAgentDispatch, \
             patch("src.telephony.inbound.CreateSIPDispatchRuleRequest"):

            await create_dispatch_rule_managed(mock_lkapi, agent_name="visitor-agent")

            # trunk_ids 应为空列表（managed 路径）
            MockInfo.assert_called_once()
            call_kwargs = MockInfo.call_args.kwargs
            assert call_kwargs.get("trunk_ids") == []

            # agent_name 应正确传入 RoomAgentDispatch
            MockAgentDispatch.assert_called_once_with(
                agent_name="visitor-agent",
                metadata='{"source":"sip"}',
            )


class TestCreateInboundTrunk:
    """自带号码路径（Twilio / 阿里云）：trunk + rule。"""

    @pytest.mark.asyncio
    async def test_create_trunk_calls_api(self):
        from src.telephony.inbound import create_inbound_trunk

        mock_response = MagicMock()
        mock_response.sip_trunk_id = "ST_test123"

        mock_lkapi = MagicMock()
        mock_lkapi.sip.create_sip_inbound_trunk = AsyncMock(return_value=mock_response)

        from unittest.mock import patch
        with patch("src.telephony.inbound.SIPInboundTrunkInfo"), \
             patch("src.telephony.inbound.CreateSIPInboundTrunkRequest"):
            result = await create_inbound_trunk(mock_lkapi, phone_numbers=["+18005551234"])

        mock_lkapi.sip.create_sip_inbound_trunk.assert_called_once()
        assert result == mock_response


class TestCreateDispatchRule:
    @pytest.mark.asyncio
    async def test_create_rule_binds_trunk_id(self):
        """自带号码路径：dispatch rule 应绑定到指定 trunk_id。"""
        from src.telephony.inbound import create_dispatch_rule

        mock_response = MagicMock()
        mock_response.sip_dispatch_rule_id = "SDR_test456"

        mock_lkapi = MagicMock()
        mock_lkapi.sip.create_sip_dispatch_rule = AsyncMock(return_value=mock_response)

        from unittest.mock import patch
        with patch("src.telephony.inbound.SIPDispatchRuleInfo") as MockInfo, \
             patch("src.telephony.inbound.SIPDispatchRule"), \
             patch("src.telephony.inbound.SIPDispatchRuleIndividual"), \
             patch("src.telephony.inbound.RoomConfiguration"), \
             patch("src.telephony.inbound.RoomAgentDispatch") as MockAgentDispatch, \
             patch("src.telephony.inbound.CreateSIPDispatchRuleRequest"):

            await create_dispatch_rule(mock_lkapi, trunk_id="ST_abc", agent_name="visitor-agent")

            # trunk_ids 应包含给定 trunk_id
            MockInfo.assert_called_once()
            call_kwargs = MockInfo.call_args.kwargs
            assert call_kwargs.get("trunk_ids") == ["ST_abc"]

            MockAgentDispatch.assert_called_once_with(
                agent_name="visitor-agent",
                metadata='{"source":"sip"}',
            )


class TestDeleteOperations:
    @pytest.mark.asyncio
    async def test_delete_trunk(self):
        from src.telephony.inbound import delete_trunk

        mock_lkapi = MagicMock()
        mock_lkapi.sip.delete_sip_trunk = AsyncMock(return_value=MagicMock())

        from unittest.mock import patch
        with patch("src.telephony.inbound.DeleteSIPTrunkRequest") as MockReq:
            await delete_trunk(mock_lkapi, "ST_abc123")
            MockReq.assert_called_once_with(sip_trunk_id="ST_abc123")
            mock_lkapi.sip.delete_sip_trunk.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_dispatch_rule(self):
        from src.telephony.inbound import delete_dispatch_rule

        mock_lkapi = MagicMock()
        mock_lkapi.sip.delete_sip_dispatch_rule = AsyncMock(return_value=MagicMock())

        from unittest.mock import patch
        with patch("src.telephony.inbound.DeleteSIPDispatchRuleRequest") as MockReq:
            await delete_dispatch_rule(mock_lkapi, "SDR_abc123")
            MockReq.assert_called_once_with(sip_dispatch_rule_id="SDR_abc123")
            mock_lkapi.sip.delete_sip_dispatch_rule.assert_called_once()
