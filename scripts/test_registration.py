#!/usr/bin/env python3
"""
直接触发一次访客登记的端到端测试脚本（无需拨打电话）。
验证"写数据库 + 推送企业微信"完整闭环。

用法:
  python scripts/test_registration.py
  python scripts/test_registration.py --plate 粤B99999 --company "测试公司" --phone 13900000000 --purpose 测试
"""
import asyncio
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    from dotenv import load_dotenv
    load_dotenv(env_path)


async def run(plate: str, company: str, phone: str, purpose: str) -> None:
    from src.data.database import init_db
    from src.tools.visitor import _do_registration

    print(f"\n{'='*50}")
    print("访客登记闭环测试")
    print(f"{'='*50}")
    print(f"  车牌号 : {plate}")
    print(f"  来访单位: {company}")
    print(f"  手机号  : {phone}")
    print(f"  来访事由: {purpose}")
    print(f"{'='*50}\n")

    # 初始化数据库（自动建表）
    await init_db()

    # 触发核心业务逻辑
    record_id = await _do_registration(plate, company, phone, purpose)

    print(f"\n{'='*50}")
    print(f"✓ 登记成功  DB record_id = {record_id}")

    # 验证记录已写入
    from src.data.database import get_session_factory
    from src.data.models import VisitorRecord
    from sqlalchemy import select

    SessionLocal = get_session_factory()
    async with SessionLocal() as session:
        result = await session.execute(
            select(VisitorRecord).where(VisitorRecord.id == record_id)
        )
        record = result.scalar_one()

    print(f"✓ DB 验证  plate={record.plate}  arrived_at={record.arrived_at}")
    print(f"{'='*50}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="直接触发一次访客登记（端到端测试）")
    parser.add_argument("--plate",   default="粤B12345",  help="车牌号")
    parser.add_argument("--company", default="测试科技有限公司", help="来访单位")
    parser.add_argument("--phone",   default="13800138000", help="手机号")
    parser.add_argument("--purpose", default="商务洽谈",  help="来访事由")
    args = parser.parse_args()

    asyncio.run(run(args.plate, args.company, args.phone, args.purpose))


if __name__ == "__main__":
    main()
