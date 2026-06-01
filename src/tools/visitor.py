import logging
from datetime import datetime

from livekit.agents import RunContext, function_tool

logger = logging.getLogger(__name__)


async def _do_registration(
    plate: str,
    company: str,
    phone: str,
    purpose: str,
) -> int:
    """
    核心业务逻辑（无 LiveKit 依赖）：写数据库 + 推送企业微信。
    与 function tool 分离，方便脚本和测试直接调用。
    返回新记录的 id。
    """
    arrived_at = datetime.now()

    # ── 写数据库 ────────────────────────────────────────────────
    from src.data.database import get_session_factory
    from src.data.models import VisitorRecord

    SessionLocal = get_session_factory()
    async with SessionLocal() as session:
        record = VisitorRecord(
            plate=plate,
            company=company,
            phone=phone,
            purpose=purpose,
            arrived_at=arrived_at,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        record_id = record.id

    logger.info("visitor saved → id=%s plate=%s phone=%s", record_id, plate, phone)

    # ── 推送企业微信 ────────────────────────────────────────────
    from src.tools.wechat import push_wechat
    await push_wechat(plate, company, phone, purpose, arrived_at)

    return record_id


@function_tool
async def submit_visitor_registration(
    context: RunContext,
    plate: str,
    company: str,
    phone: str,
    purpose: str,
) -> str:
    """登记访客信息。4 项信息全部确认后立即调用，不要等通话结束。

    Args:
        plate (str): 车牌号，例如 粤B12345
        company (str): 来访单位名称
        phone (str): 联系手机号，11位数字
        purpose (str): 来访事由
    """
    try:
        record_id = await _do_registration(plate, company, phone, purpose)
        logger.info("registration complete: record_id=%s", record_id)
        return f"登记成功，编号 {record_id}，已通知门卫。"
    except Exception as exc:
        logger.exception("registration failed: %s", exc)
        # 返回错误信息，让模型告知用户
        return f"登记出现问题，请联系前台。({type(exc).__name__})"
