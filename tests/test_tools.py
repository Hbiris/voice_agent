"""wechat 推送和 DB 写入的单元测试（不依赖外部服务）。"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock


# ─────────────────────────────────────────────────────────────────────────────
# WeChat
# ─────────────────────────────────────────────────────────────────────────────

class TestWechatPayload:
    def test_payload_format(self):
        """推送 payload 应为 markdown 格式，包含所有访客字段。"""
        from src.tools.wechat import _build_payload

        ts = datetime(2026, 6, 2, 10, 30, 0)
        payload = _build_payload("粤B12345", "测试科技", "13800138000", "商务洽谈", ts)

        assert payload["msgtype"] == "markdown"
        content = payload["markdown"]["content"]
        assert "粤B12345" in content
        assert "测试科技" in content
        assert "13800138000" in content
        assert "商务洽谈" in content
        assert "2026-06-02 10:30:00" in content

    @pytest.mark.asyncio
    async def test_dry_run_when_no_webhook_url(self, caplog):
        """WECHAT_WEBHOOK_URL 未设置时应打印日志，不发 HTTP 请求。"""
        import logging
        from src.tools.wechat import push_wechat

        ts = datetime(2026, 6, 2, 10, 30, 0)

        with patch("src.tools.wechat.get_settings") as mock_settings:
            mock_settings.return_value.wechat_webhook_url = ""
            with caplog.at_level(logging.INFO, logger="src.tools.wechat"):
                await push_wechat("粤B12345", "测试科技", "13800138000", "商务洽谈", ts)

        assert "[dry-run]" in caplog.text
        assert "粤B12345" in caplog.text

    @pytest.mark.asyncio
    async def test_sends_post_when_url_configured(self):
        """WECHAT_WEBHOOK_URL 已设置时应 POST 到该地址，errcode=0 视为成功。"""
        from src.tools.wechat import push_wechat

        ts = datetime(2026, 6, 2, 10, 30, 0)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"errcode": 0, "errmsg": "ok"})

        with patch("src.tools.wechat.get_settings") as mock_settings:
            mock_settings.return_value.wechat_webhook_url = "https://example.com/webhook"
            with patch("httpx.AsyncClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_resp)
                MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

                await push_wechat("粤B12345", "测试科技", "13800138000", "商务洽谈", ts)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args.args[0] == "https://example.com/webhook"
        payload = call_args.kwargs["json"]
        assert payload["msgtype"] == "markdown"

    @pytest.mark.asyncio
    async def test_raises_on_wechat_errcode(self):
        """企业微信返回 errcode != 0 时应抛出 RuntimeError（HTTP 200 不代表成功）。"""
        from src.tools.wechat import push_wechat

        ts = datetime(2026, 6, 2, 10, 30, 0)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"errcode": 93000, "errmsg": "invalid webhook url"})

        with patch("src.tools.wechat.get_settings") as mock_settings:
            mock_settings.return_value.wechat_webhook_url = "https://example.com/webhook"
            with patch("httpx.AsyncClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.post = AsyncMock(return_value=mock_resp)
                MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

                with pytest.raises(RuntimeError, match="errcode=93000"):
                    await push_wechat("粤B12345", "测试科技", "13800138000", "商务洽谈", ts)


# ─────────────────────────────────────────────────────────────────────────────
# 数据库写入
# ─────────────────────────────────────────────────────────────────────────────

class TestDatabaseWrite:
    @pytest.mark.asyncio
    async def test_visitor_record_saved_to_db(self):
        """_do_registration 应把访客记录写入数据库，并返回有效 id。"""
        from src.data.database import init_db, get_session_factory
        from src.data.models import VisitorRecord
        from sqlalchemy import select

        # 使用内存 SQLite，与真实 DB 隔离
        with patch("src.data.database._resolve_url", return_value="sqlite+aiosqlite:///:memory:"):
            # 重置模块全局状态
            import src.data.database as db_mod
            db_mod._engine = None
            db_mod._SessionLocal = None

            await init_db()

            # 关闭 wechat 推送（dry-run）
            with patch("src.tools.wechat.get_settings") as mock_settings:
                mock_settings.return_value.wechat_webhook_url = ""

                from src.tools.visitor import _do_registration
                record_id = await _do_registration(
                    plate="京A00001",
                    company="示例公司",
                    phone="13900000001",
                    purpose="送货",
                )

            assert isinstance(record_id, int)
            assert record_id > 0

            # 验证记录真实写入
            SessionLocal = get_session_factory()
            async with SessionLocal() as session:
                result = await session.execute(
                    select(VisitorRecord).where(VisitorRecord.id == record_id)
                )
                record = result.scalar_one()

            assert record.plate == "京A00001"
            assert record.company == "示例公司"
            assert record.phone == "13900000001"
            assert record.purpose == "送货"
            assert record.arrived_at is not None

    @pytest.mark.asyncio
    async def test_multiple_records_have_distinct_ids(self):
        """连续写入两条记录，id 应不同。"""
        with patch("src.data.database._resolve_url", return_value="sqlite+aiosqlite:///:memory:"):
            import src.data.database as db_mod
            db_mod._engine = None
            db_mod._SessionLocal = None

            from src.data.database import init_db
            await init_db()

            with patch("src.tools.wechat.get_settings") as mock_settings:
                mock_settings.return_value.wechat_webhook_url = ""
                from src.tools.visitor import _do_registration
                id1 = await _do_registration("粤B00001", "公司A", "13800000001", "送货")
                id2 = await _do_registration("粤B00002", "公司B", "13800000002", "开会")

            assert id1 != id2


# ─────────────────────────────────────────────────────────────────────────────
# 工具结构
# ─────────────────────────────────────────────────────────────────────────────

class TestSubmitToolStructure:
    def test_tool_is_function_tool(self):
        """submit_visitor_registration 应是 FunctionTool 类型。"""
        from livekit.agents.llm import FunctionTool
        from src.tools.visitor import submit_visitor_registration
        assert isinstance(submit_visitor_registration, FunctionTool)

    def test_tool_has_correct_name(self):
        from src.tools.visitor import submit_visitor_registration
        assert submit_visitor_registration.info.name == "submit_visitor_registration"

    def test_tool_description_not_empty(self):
        from src.tools.visitor import submit_visitor_registration
        assert len(submit_visitor_registration.info.description) > 10
