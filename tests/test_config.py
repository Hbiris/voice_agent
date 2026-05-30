"""配置加载与 profile 选择的单元测试（不依赖外部服务）。"""
import pytest
from unittest.mock import patch


class TestSettings:
    def test_defaults(self):
        """无 .env 时默认值正确。"""
        # 清除 lru_cache，隔离测试
        from src.config.settings import get_settings
        get_settings.cache_clear()

        with patch.dict("os.environ", {}, clear=True):
            # 不读取真实 .env
            with patch("src.config.settings.Settings.model_config", {"extra": "ignore"}):
                s = get_settings.__wrapped__()  # bypass cache
                assert s.voice_profile == "demo"
                assert s.agent_name == "visitor-agent"
                assert s.sip_room_prefix == "call-"

    def test_env_override(self):
        """环境变量能正确覆盖默认值。"""
        from src.config.settings import Settings

        with patch.dict("os.environ", {
            "VOICE_PROFILE": "china_landing",
            "LIVEKIT_URL": "wss://test.livekit.cloud",
            "LIVEKIT_API_KEY": "key123",
            "LIVEKIT_API_SECRET": "secret456",
            "AGENT_NAME": "test-agent",
        }):
            s = Settings()
            assert s.voice_profile == "china_landing"
            assert s.livekit_url == "wss://test.livekit.cloud"
            assert s.agent_name == "test-agent"


class TestProfile:
    def test_demo_profile(self):
        from src.config.profiles import Profile, get_profile
        from src.config.settings import get_settings
        get_settings.cache_clear()

        with patch.dict("os.environ", {"VOICE_PROFILE": "demo"}):
            assert get_profile() == Profile.DEMO
            assert get_profile() == "demo"  # str comparison via str Enum

    def test_china_landing_profile(self):
        from src.config.profiles import Profile, get_profile
        from src.config.settings import get_settings
        get_settings.cache_clear()

        with patch.dict("os.environ", {"VOICE_PROFILE": "china_landing"}):
            assert get_profile() == Profile.CHINA_LANDING

    def test_invalid_profile_raises(self):
        from src.config.profiles import get_profile, Profile
        from src.config.settings import get_settings
        get_settings.cache_clear()

        with patch.dict("os.environ", {"VOICE_PROFILE": "nonexistent"}):
            with pytest.raises(ValueError):
                get_profile()

    def test_profile_enum_values(self):
        from src.config.profiles import Profile
        assert Profile.DEMO.value == "demo"
        assert Profile.CHINA_LANDING.value == "china_landing"


class TestVoiceFactory:
    def test_unknown_profile_raises(self):
        """factory 对未知 profile 应抛出 ValueError。"""
        from src.config.settings import get_settings
        get_settings.cache_clear()

        with patch("src.voice.factory.get_profile") as mock_profile:
            mock_profile.return_value = "unknown_profile"
            from src.voice.factory import build_voice_kwargs
            with pytest.raises((ValueError, Exception)):
                build_voice_kwargs()

    def test_demo_factory_dispatches(self):
        """demo profile 应调用 demo 模块的 build_voice_kwargs。"""
        from src.config.profiles import Profile

        with patch("src.voice.factory.get_profile", return_value=Profile.DEMO):
            with patch("src.voice.profiles.demo.build_voice_kwargs", return_value={"llm": "mock_llm"}) as mock_build:
                from src.voice import factory
                # 重新导入以清除模块缓存中的函数引用
                import importlib
                importlib.reload(factory)
                with patch("src.voice.factory.get_profile", return_value=Profile.DEMO):
                    with patch("src.voice.profiles.demo.build_voice_kwargs", return_value={"llm": "mock_llm"}) as mb:
                        result = factory.build_voice_kwargs()
                        assert "llm" in result
