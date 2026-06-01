import logging
from datetime import datetime

import httpx

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


def _build_payload(
    plate: str,
    company: str,
    phone: str,
    purpose: str,
    arrived_at: datetime,
) -> dict:
    content = (
        "## 🚗 新访客登记\n"
        f"> **车牌号**：{plate}\n"
        f"> **来访单位**：{company}\n"
        f"> **联系手机**：{phone}\n"
        f"> **来访事由**：{purpose}\n"
        f"> **入场时间**：{arrived_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        "请保安确认后放行。"
    )
    return {"msgtype": "markdown", "markdown": {"content": content}}


async def push_wechat(
    plate: str,
    company: str,
    phone: str,
    purpose: str,
    arrived_at: datetime,
) -> None:
    """
    推送访客信息到企业微信群机器人。
    WECHAT_WEBHOOK_URL 未配置时 dry-run：把消息内容打印到日志，不发网络请求。
    """
    payload = _build_payload(plate, company, phone, purpose, arrived_at)
    webhook_url = get_settings().wechat_webhook_url

    if not webhook_url:
        logger.info(
            "[dry-run] WeChat push (WECHAT_WEBHOOK_URL not set):\n%s",
            payload["markdown"]["content"],
        )
        return

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(webhook_url, json=payload)
        resp.raise_for_status()
        logger.info("WeChat push OK: status=%d", resp.status_code)
