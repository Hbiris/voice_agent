#!/usr/bin/env python3
"""
SIP trunk + dispatch rule 一次性配置脚本。
运行前确保 .env 已填写 LIVEKIT_* 和电话号码相关变量。

用法:
  python scripts/setup_sip_trunk.py                     # 完整配置（trunk + rule）
  python scripts/setup_sip_trunk.py --list              # 列出已有 trunk 和 rule
  python scripts/setup_sip_trunk.py --provider twilio   # 使用 Twilio IP 白名单
"""
import asyncio
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def run(args: argparse.Namespace) -> None:
    from livekit.api import LiveKitAPI
    from src.config.settings import get_settings
    from src.telephony.inbound import (
        TWILIO_SIP_IPS,
        create_inbound_trunk,
        create_dispatch_rule,
        list_trunks,
        list_dispatch_rules,
    )

    settings = get_settings()

    if not settings.livekit_url:
        sys.exit("ERROR: LIVEKIT_URL not set in environment / .env")

    lkapi = LiveKitAPI(
        url=settings.livekit_url,
        api_key=settings.livekit_api_key,
        api_secret=settings.livekit_api_secret,
    )

    async with lkapi:
        if args.list:
            trunks = await list_trunks(lkapi)
            rules = await list_dispatch_rules(lkapi)
            print(f"\n=== SIP Inbound Trunks ({len(trunks)}) ===")
            for t in trunks:
                print(f"  {t.sip_trunk_id}  {t.name}  numbers={t.numbers}")
            print(f"\n=== SIP Dispatch Rules ({len(rules)}) ===")
            for r in rules:
                print(f"  {r.sip_dispatch_rule_id}  {r.name}")
            return

        # ── 确定电话号码 ──────────────────────────────────────────
        phone_numbers: list[str] = []
        if settings.twilio_phone_number:
            phone_numbers.append(settings.twilio_phone_number)
        elif settings.aliyun_phone_number:
            # china_landing 路径（落地时启用）
            phone_numbers.append(settings.aliyun_phone_number)
        else:
            sys.exit(
                "ERROR: no phone number found.\n"
                "Set TWILIO_PHONE_NUMBER (demo) or ALIYUN_PHONE_NUMBER (china_landing) in .env"
            )

        # ── 确定 IP 白名单 ─────────────────────────────────────────
        allowed_ips: list[str] | None = None
        if args.provider == "twilio":
            allowed_ips = TWILIO_SIP_IPS
            logger.info("using Twilio SIP IP allowlist")
        elif args.provider == "aliyun":
            from src.telephony.inbound import ALIYUN_SIP_IPS
            if not ALIYUN_SIP_IPS:
                logger.warning("ALIYUN_SIP_IPS is empty — fill in src/telephony/inbound.py first")
            allowed_ips = ALIYUN_SIP_IPS
        else:
            logger.info("provider=livekit-managed, no IP allowlist needed")

        # ── 创建 trunk ─────────────────────────────────────────────
        trunk = await create_inbound_trunk(
            lkapi,
            phone_numbers=phone_numbers,
            allowed_ips=allowed_ips,
        )

        # ── 创建 dispatch rule ─────────────────────────────────────
        await create_dispatch_rule(
            lkapi,
            trunk_id=trunk.sip_trunk_id,
            agent_name=settings.agent_name,
            room_prefix=settings.sip_room_prefix,
        )

        logger.info("SIP setup complete — dial %s to test", phone_numbers)


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure SIP trunk and dispatch rule")
    parser.add_argument("--list", action="store_true", help="List existing trunks and rules")
    parser.add_argument(
        "--provider",
        choices=["livekit", "twilio", "aliyun"],
        default="livekit",
        help="SIP provider (affects IP allowlist). Default: livekit (managed, no allowlist)",
    )
    args = parser.parse_args()

    # 加载 .env
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        from dotenv import load_dotenv
        load_dotenv(env_path)

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
