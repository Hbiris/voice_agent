"""
SIP 来电接入：创建 inbound trunk + dispatch rule。
运行一次（非启动时热路径）：python scripts/setup_sip_trunk.py
"""
import logging
from typing import Any

from livekit.api import (
    CreateSIPInboundTrunkRequest,
    SIPInboundTrunkInfo,
    CreateSIPDispatchRuleRequest,
    SIPDispatchRuleInfo,
    SIPDispatchRule,
    SIPDispatchRuleIndividual,
    RoomConfiguration,
    RoomAgentDispatch,
    ListSIPInboundTrunkRequest,
    ListSIPDispatchRuleRequest,
)

logger = logging.getLogger(__name__)

# ── Twilio Elastic SIP Trunk 信令 IP 段（demo 备选方案）────────────────────────
# 来源：https://www.twilio.com/docs/sip-trunking/ip-addresses
TWILIO_SIP_IPS: list[str] = [
    "54.172.60.0/30",
    "54.244.51.0/30",
    "54.171.127.192/30",
    "35.156.191.128/30",
    "35.166.193.128/30",
    "54.65.63.192/30",
    "54.169.127.128/30",
    "54.252.254.64/30",
    "177.71.206.192/30",
]

# ── 阿里云 SIP 信令 IP（china_landing 落地时填入）────────────────────────────
# TODO (china_landing): 从阿里云文档获取实际 IP 段并填入此列表。
# 参考文档：https://help.aliyun.com/product/30071.html（云通信语音服务）
ALIYUN_SIP_IPS: list[str] = []  # TODO: fill before china_landing deployment


async def create_inbound_trunk(
    lkapi: Any,
    phone_numbers: list[str],
    allowed_ips: list[str] | None = None,
    name: str = "visitor-trunk",
) -> Any:
    """
    创建 SIP inbound trunk。

    provider 对应关系：
    - demo / LiveKit Phone Numbers：allowed_ips=None（LiveKit 托管，无需 IP 白名单）
    - demo / Twilio：allowed_ips=TWILIO_SIP_IPS
    - china_landing / 阿里云：allowed_ips=ALIYUN_SIP_IPS（落地时替换）
    """
    trunk = SIPInboundTrunkInfo(
        name=name,
        numbers=phone_numbers,
        allowed_addresses=allowed_ips or [],
        krisp_enabled=True,
    )
    response = await lkapi.sip.create_sip_inbound_trunk(
        CreateSIPInboundTrunkRequest(trunk=trunk)
    )
    logger.info("created inbound trunk: id=%s  numbers=%s", response.sip_trunk_id, phone_numbers)
    return response


async def create_dispatch_rule(
    lkapi: Any,
    trunk_id: str,
    agent_name: str = "visitor-agent",
    room_prefix: str = "call-",
) -> Any:
    """
    创建 SIP dispatch rule：每路来电 → 独立 room → 显式 dispatch agent_name。

    agent_name 必须与 WorkerOptions(agent_name=...) 完全一致。

    china_landing 替换说明：
      - trunk_id 换成阿里云 SIP trunk 的 id（create_inbound_trunk 返回值中的 sip_trunk_id）
      - agent_name / room_prefix 不变（业务逻辑与 SIP provider 无关）
    """
    rule_info = SIPDispatchRuleInfo(
        name="visitor-dispatch",
        trunk_ids=[trunk_id],
        rule=SIPDispatchRule(
            dispatch_rule_individual=SIPDispatchRuleIndividual(
                room_prefix=room_prefix,
                pin="",
            )
        ),
        room_config=RoomConfiguration(
            agents=[
                RoomAgentDispatch(
                    agent_name=agent_name,
                    metadata='{"source":"sip"}',
                )
            ]
        ),
    )
    response = await lkapi.sip.create_sip_dispatch_rule(
        CreateSIPDispatchRuleRequest(dispatch_rule=rule_info)
    )
    logger.info(
        "created dispatch rule: id=%s  agent=%s",
        response.sip_dispatch_rule_id,
        agent_name,
    )
    return response


async def list_trunks(lkapi: Any) -> list[Any]:
    """列出所有已配置的 SIP inbound trunk（用于调试和幂等检查）。"""
    response = await lkapi.sip.list_sip_inbound_trunk(ListSIPInboundTrunkRequest())
    return list(response.items)


async def list_dispatch_rules(lkapi: Any) -> list[Any]:
    """列出所有已配置的 SIP dispatch rule（用于调试和幂等检查）。"""
    response = await lkapi.sip.list_sip_dispatch_rule(ListSIPDispatchRuleRequest())
    return list(response.items)
