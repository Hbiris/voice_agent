#!/usr/bin/env python3
"""
SIP trunk + dispatch rule 配置脚本（一次性运行）。

用法:
  python scripts/setup_sip_trunk.py                       # 创建 managed dispatch rule（LiveKit 托管号，默认）
  python scripts/setup_sip_trunk.py --provider twilio     # 创建 trunk + rule（Twilio 自带号）
  python scripts/setup_sip_trunk.py --provider aliyun     # 创建 trunk + rule（阿里云落地）
  python scripts/setup_sip_trunk.py --list                # 列出所有 trunk 和 dispatch rule
  python scripts/setup_sip_trunk.py --cleanup             # 删除多余 trunk 和重复 rule（保留第一条）
  python scripts/setup_sip_trunk.py --cleanup --yes       # 同上，跳过确认提示
"""
import asyncio
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _print_state(trunks: list, rules: list) -> None:
    print(f"\n=== SIP Inbound Trunks ({len(trunks)}) ===")
    for t in trunks:
        print(f"  {t.sip_trunk_id}  {t.name}  numbers={list(t.numbers)}")
    print(f"\n=== SIP Dispatch Rules ({len(rules)}) ===")
    for r in rules:
        agents = []
        if r.room_config and r.room_config.agents:
            agents = [a.agent_name for a in r.room_config.agents]
        trunk_ids = list(r.trunk_ids)
        print(f"  {r.sip_dispatch_rule_id}  {r.name}  agents={agents}  trunk_ids={trunk_ids}")


async def run(args: argparse.Namespace) -> None:
    from livekit.api import LiveKitAPI
    from src.config.settings import get_settings
    from src.telephony.inbound import (
        TWILIO_SIP_IPS, ALIYUN_SIP_IPS,
        create_dispatch_rule_managed,
        create_inbound_trunk,
        create_dispatch_rule,
        delete_trunk,
        delete_dispatch_rule,
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
        # ── --list ────────────────────────────────────────────────────────────
        if args.list:
            trunks = await list_trunks(lkapi)
            rules = await list_dispatch_rules(lkapi)
            _print_state(trunks, rules)
            return

        # ── --cleanup ─────────────────────────────────────────────────────────
        if args.cleanup:
            trunks = await list_trunks(lkapi)
            rules = await list_dispatch_rules(lkapi)

            print("=== BEFORE CLEANUP ===")
            _print_state(trunks, rules)

            # 找出需要删除的内容
            trunks_to_delete = list(trunks)  # livekit 托管路径：所有自建 trunk 都应删除

            # dispatch rules：保留第一条（最老的），删除其余重复
            rules_to_delete = rules[1:] if len(rules) > 1 else []
            rule_to_keep = rules[0] if rules else None

            if not trunks_to_delete and not rules_to_delete:
                print("\nNothing to clean up — state is already clean.")
                return

            print("\n=== CLEANUP PLAN ===")
            for t in trunks_to_delete:
                print(f"  DELETE trunk:  {t.sip_trunk_id}  ({t.name})")
            for r in rules_to_delete:
                print(f"  DELETE rule:   {r.sip_dispatch_rule_id}  ({r.name})")
            if rule_to_keep:
                print(f"  KEEP   rule:   {rule_to_keep.sip_dispatch_rule_id}  ({rule_to_keep.name})")

            if not args.yes:
                confirm = input("\nProceed? [y/N] ").strip().lower()
                if confirm != "y":
                    print("Aborted.")
                    return

            for t in trunks_to_delete:
                await delete_trunk(lkapi, t.sip_trunk_id)
            for r in rules_to_delete:
                await delete_dispatch_rule(lkapi, r.sip_dispatch_rule_id)

            print("\n=== AFTER CLEANUP ===")
            _print_state(await list_trunks(lkapi), await list_dispatch_rules(lkapi))
            return

        # ── 创建（provider-specific）──────────────────────────────────────────
        if args.provider == "livekit":
            # LiveKit 托管号：只建 dispatch rule，无需 trunk 也无需电话号码变量
            await create_dispatch_rule_managed(
                lkapi,
                agent_name=settings.agent_name,
                room_prefix=settings.sip_room_prefix,
            )
            print(f"\nDone. Dial your LiveKit Phone Number to test (agent: {settings.agent_name})")

        elif args.provider == "twilio":
            if not settings.twilio_phone_number:
                sys.exit("ERROR: TWILIO_PHONE_NUMBER not set in .env")
            trunk = await create_inbound_trunk(
                lkapi,
                phone_numbers=[settings.twilio_phone_number],
                allowed_ips=TWILIO_SIP_IPS,
            )
            await create_dispatch_rule(
                lkapi,
                trunk_id=trunk.sip_trunk_id,
                agent_name=settings.agent_name,
                room_prefix=settings.sip_room_prefix,
            )
            print(f"\nDone. Dial {settings.twilio_phone_number} to test.")

        elif args.provider == "aliyun":
            if not settings.aliyun_phone_number:
                sys.exit("ERROR: ALIYUN_PHONE_NUMBER not set in .env")
            if not ALIYUN_SIP_IPS:
                logger.warning("ALIYUN_SIP_IPS is empty — fill in src/telephony/inbound.py first")
            trunk = await create_inbound_trunk(
                lkapi,
                phone_numbers=[settings.aliyun_phone_number],
                allowed_ips=ALIYUN_SIP_IPS,
                name="visitor-trunk-aliyun",
            )
            await create_dispatch_rule(
                lkapi,
                trunk_id=trunk.sip_trunk_id,
                agent_name=settings.agent_name,
                room_prefix=settings.sip_room_prefix,
            )
            print(f"\nDone. Dial {settings.aliyun_phone_number} to test.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure SIP trunk and dispatch rule")
    parser.add_argument("--list", action="store_true", help="List existing trunks and rules")
    parser.add_argument(
        "--provider",
        choices=["livekit", "twilio", "aliyun"],
        default="livekit",
        help="SIP provider (default: livekit — managed numbers, dispatch rule only)",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete all self-built trunks and duplicate dispatch rules, keeping the first rule",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt in --cleanup mode",
    )
    args = parser.parse_args()

    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
        except ImportError:
            pass

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
