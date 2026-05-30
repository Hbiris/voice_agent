"""
SIP 来电接入：创建 / 删除 inbound trunk + dispatch rule。

两条路径：
  --provider livekit  (默认): LiveKit 托管号，无需 trunk，只建 dispatch rule
  --provider twilio / aliyun : 自带号码，需先建 trunk 再建 dispatch rule

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
    DeleteSIPTrunkRequest,
    DeleteSIPDispatchRuleRequest,
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
# TODO (china_landing): 从阿里云文档获取实际 IP 段并填入。
ALIYUN_SIP_IPS: list[str] = []


# ─────────────────────────────────────────────────────────────────────────────
# 创建操作
# ─────────────────────────────────────────────────────────────────────────────

async def create_dispatch_rule_managed(
    lkapi: Any,
    agent_name: str = "visitor-agent",
    room_prefix: str = "call-",
) -> Any:
    """
    LiveKit 托管号路径：创建 dispatch rule，trunk_ids=[] 匹配所有托管号来电。
    不创建 trunk — LiveKit Phone Numbers 自动处理路由。
    """
    rule_info = SIPDispatchRuleInfo(
        name="visitor-dispatch",
        trunk_ids=[],  # 空 = 匹配所有托管号，无需指定 trunk
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
    logger.info("created dispatch rule (managed): id=%s  agent=%s", response.sip_dispatch_rule_id, agent_name)
    return response


async def create_inbound_trunk(
    lkapi: Any,
    phone_numbers: list[str],
    allowed_ips: list[str] | None = None,
    name: str = "visitor-trunk",
) -> Any:
    """
    自带号码路径（Twilio / 阿里云）：创建 SIP inbound trunk。

    - Twilio: allowed_ips=TWILIO_SIP_IPS
    - 阿里云: allowed_ips=ALIYUN_SIP_IPS（china_landing 落地时填入）
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
    自带号码路径（Twilio / 阿里云）：创建绑定到特定 trunk 的 dispatch rule。

    china_landing 替换说明：trunk_id 换成阿里云 trunk 的 sip_trunk_id，其余不变。
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
    logger.info("created dispatch rule: id=%s  agent=%s", response.sip_dispatch_rule_id, agent_name)
    return response


# ─────────────────────────────────────────────────────────────────────────────
# 删除操作
# ─────────────────────────────────────────────────────────────────────────────

async def delete_trunk(lkapi: Any, trunk_id: str) -> None:
    await lkapi.sip.delete_sip_trunk(DeleteSIPTrunkRequest(sip_trunk_id=trunk_id))
    logger.info("deleted trunk: %s", trunk_id)


async def delete_dispatch_rule(lkapi: Any, rule_id: str) -> None:
    await lkapi.sip.delete_sip_dispatch_rule(DeleteSIPDispatchRuleRequest(sip_dispatch_rule_id=rule_id))
    logger.info("deleted dispatch rule: %s", rule_id)


# ─────────────────────────────────────────────────────────────────────────────
# 查询操作
# ─────────────────────────────────────────────────────────────────────────────

async def list_trunks(lkapi: Any) -> list[Any]:
    response = await lkapi.sip.list_sip_inbound_trunk(ListSIPInboundTrunkRequest())
    return list(response.items)


async def list_dispatch_rules(lkapi: Any) -> list[Any]:
    response = await lkapi.sip.list_sip_dispatch_rule(ListSIPDispatchRuleRequest())
    return list(response.items)
