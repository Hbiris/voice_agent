import logging
import re
import time
from datetime import datetime

from livekit.agents import RunContext, function_tool

logger = logging.getLogger(__name__)

# ── 反编造校验 ──────────────────────────────────────────────────────────────────
# CJK字 + 字母 + 4~5位字母数字 = 标准车牌格式，允许 ASR 同音错字（"月"代"粤"等）
_PLATE_RE = re.compile(r"[一-鿿][A-Za-z][A-Za-z0-9]{4,5}")

# 中文数字 → 阿拉伯数字的字符映射表（用于手机号归一化）
_ZH_DIGIT_TABLE = str.maketrans(
    "零〇一壹幺二贰两三叁四肆五伍六陆七柒八捌九玖",
    "0011122233445566778899",
)


def _normalize_digits(text: str) -> str:
    """中文数字转阿拉伯数字，再去掉所有非数字字符，返回纯数字串。

    处理 STT 常见格式：
      - 连字符/空格分隔："133-1234-1234" / "133 1234 1234" → "13312341234"
      - 中文数字："一三三一二三四一二三四" → "13312341234"
      - 幺："幺三三…" → "133…"（幺=1）
    """
    return re.sub(r"\D", "", text.translate(_ZH_DIGIT_TABLE))

_FIELD_NAMES = {"plate": "车牌号", "phone": "手机号", "company": "来访单位", "purpose": "来访事由"}


_PHONE_DIGITS_RE = re.compile(r"\d{7,}")


def _check_transcript_evidence(
    transcripts: list[str],
    plate: str,
    company: str,   # noqa: ARG001 — reserved for future stricter check
    phone: str,
    purpose: str,   # noqa: ARG001 — reserved for future stricter check
) -> list[str]:
    """
    反编造校验：检查每个字段在来电者转写里有无来源证据。
    返回缺证据的字段名列表（空列表表示全部通过）。

    原则：只挡"凭空捏造"（转写里该类信息完全没有），不挡"STT 听岔"
    （转写里有、但某位数字被识别错误）。

    - 车牌：转写里出现"汉字+字母+4~5位字母数字"的车牌格式即视为有证据
           （省份字同音写错如"月D88888"格式仍匹配）。
           备用：提交车牌的字母+数字后缀（如 "D88888"）出现在转写中。
    - 手机：把转写里所有文字归一化为数字串（含中文数字转换），只要存在
           连续 ≥7 位的数字段（说明来电者确实报了号），即放行；
           不做精确子串匹配，因为 STT 偶尔会错几位。
    - 来访单位/事由：转写非空（来电者说过话）即视为有证据。
    """
    combined = " ".join(transcripts).strip()
    combined_nospace = combined.replace(" ", "")

    if len(combined) < 2:
        return ["plate", "phone", "company", "purpose"]

    failures: list[str] = []

    # 车牌
    if not _PLATE_RE.search(combined_nospace):
        suffix_m = re.search(r"[A-Za-z][A-Za-z0-9]{4,5}$", plate)
        if not (suffix_m and suffix_m.group().upper() in combined_nospace.upper()):
            failures.append("plate")

    # 手机：存在性判断——转写归一化数字串中有 ≥7 位连续数字即证明来电者报过号
    norm_transcript = _normalize_digits(combined)
    norm_phone = _normalize_digits(phone)
    logger.debug(
        "[anti-fab phone] transcript_digits=%r  submitted_digits=%r",
        norm_transcript, norm_phone,
    )
    if not norm_phone or not _PHONE_DIGITS_RE.search(norm_transcript):
        failures.append("phone")

    # 来访单位/事由：转写非空已由上方 len(combined) >= 2 保证

    return failures


async def _do_registration(
    plate: str,
    company: str,
    phone: str,
    purpose: str,
    caller_id: str | None = None,
) -> int:
    """
    核心业务逻辑（无 LiveKit 依赖）：写数据库 + 推送企业微信。
    与 function tool 分离，方便脚本和测试直接调用。
    返回新记录的 id。
    """
    t0 = time.perf_counter()
    arrived_at = datetime.now()

    # ── 写数据库 ────────────────────────────────────────────────
    from src.data.database import get_session_factory
    from src.data.models import VisitorRecord

    SessionLocal = get_session_factory()
    t_db0 = time.perf_counter()
    async with SessionLocal() as session:
        record = VisitorRecord(
            plate=plate,
            company=company,
            phone=phone,
            purpose=purpose,
            arrived_at=arrived_at,
            caller_id=caller_id,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        record_id = record.id
    t_db1 = time.perf_counter()

    logger.info(
        "visitor saved → id=%s plate=%s phone=%s [db_write=%.0fms]",
        record_id, plate, phone, (t_db1 - t_db0) * 1000,
    )

    # ── 推送企业微信 ────────────────────────────────────────────
    from src.tools.wechat import push_wechat
    t_wx0 = time.perf_counter()
    await push_wechat(plate, company, phone, purpose, arrived_at)
    t_wx1 = time.perf_counter()

    logger.info(
        "_do_registration done → id=%s [total=%.0fms db=%.0fms wechat=%.0fms]",
        record_id,
        (t_wx1 - t0) * 1000,
        (t_db1 - t_db0) * 1000,
        (t_wx1 - t_wx0) * 1000,
    )
    return record_id


@function_tool
async def submit_visitor_registration(
    context: RunContext,
    plate: str,
    company: str,
    phone: str,
    purpose: str,
    reused_from_caller_history: bool = False,
) -> str:
    """登记访客信息。4 项信息全部确认后立即调用，不要等通话结束。

    Args:
        plate (str): 车牌号，例如 粤B12345
        company (str): 来访单位名称
        phone (str): 联系手机号，11位数字
        purpose (str): 来访事由
        reused_from_caller_history (bool): 回访复用历史记录时设为 True（来电者已口头确认上次信息
            不变，四项值直接取历史记录）；跳过"本次转写要有该值"的反编造检查。首次来访保持 False。
    """
    t_tool = time.perf_counter()

    # 读通话计时器（仅真实通话场景有；直接调用脚本时 userdata 可能未设置）
    try:
        from src.agent.worker import CallTimer
        timer: CallTimer | None = context.userdata
    except Exception:
        timer = None

    if timer is not None:
        timer.t_tool_submitted = t_tool  # 供 _on_close 计算 wall_clock 用
        conversation_ms = (t_tool - timer.t_connected) * 1000
        logger.info(
            "[timing] tool invoked — conversation=%.0fms (connect→tool)",
            conversation_ms,
        )

    # ── 反编造校验 ─────────────────────────────────────────────────────────────
    # 历史复用路径：值来自数据库记录 + 来电者口头确认，不要求本次转写包含该值
    if reused_from_caller_history:
        logger.info(
            "anti-fabrication SKIPPED (reused_from_caller_history) plate=%r phone=%r",
            plate, phone,
        )
    else:
        transcripts = timer.transcripts if timer is not None else []
        failures = _check_transcript_evidence(transcripts, plate, company, phone, purpose)
        if failures:
            missing = "、".join(_FIELD_NAMES[f] for f in failures)
            logger.warning(
                "anti-fabrication REJECTED: fields=%s  plate=%r phone=%r transcripts=%r",
                failures, plate, phone, transcripts,
            )
            return f"校验未通过：{missing}在通话转写中无来源证据，请重新向来电者确认这些信息。"

    caller_id = timer.caller_id if timer is not None else None

    try:
        record_id = await _do_registration(plate, company, phone, purpose, caller_id=caller_id)
        t_done = time.perf_counter()
        server_ms = (t_done - t_tool) * 1000
        logger.info(
            "submit_visitor_registration OK → id=%s [server=%.0fms]",
            record_id, server_ms,
        )
        if timer is not None:
            timer.t_wechat_sent = t_done
            cold_start_ms = (timer.t_greeting - timer.t_connected) * 1000
            budget_ms = (t_done - timer.t_greeting) * 1000
            logger.info(
                "[timing] cold_start=%.0fms(不计入预算)  budget=%.0fms(25s指标)"
                "  server=%.0fms",
                cold_start_ms, budget_ms, server_ms,
            )
        return f"登记成功，编号 {record_id}，已通知门卫。"
    except Exception as exc:
        server_ms = (time.perf_counter() - t_tool) * 1000
        logger.exception(
            "submit_visitor_registration FAILED [server=%.0fms]: %s", server_ms, exc,
        )
        return f"登记出现问题，请联系前台。({type(exc).__name__})"
