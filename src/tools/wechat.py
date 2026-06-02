import logging
import time
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

    t0 = time.perf_counter()

    if not webhook_url:
        logger.info(
            "[dry-run] WeChat push (WECHAT_WEBHOOK_URL not set) [%.0fms]:\n%s",
            (time.perf_counter() - t0) * 1000,
            payload["markdown"]["content"],
        )
        return

    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(webhook_url, json=payload)
        resp.raise_for_status()  # 捕获真实 HTTP 错误（非 200）
        body = resp.json()
        errcode = body.get("errcode", -1)
        if errcode != 0:
            errmsg = body.get("errmsg", "unknown")
            raise RuntimeError(f"WeChat webhook rejected: errcode={errcode} errmsg={errmsg}")
        logger.info("WeChat push OK: errcode=0 [%.0fms]", (time.perf_counter() - t0) * 1000)
