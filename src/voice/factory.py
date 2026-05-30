from typing import Any

from src.config.profiles import Profile, get_profile


def build_voice_kwargs() -> dict[str, Any]:
    """根据当前 VOICE_PROFILE 返回对应语音栈的 AgentSession kwargs。"""
    profile = get_profile()

    if profile == Profile.DEMO:
        from src.voice.profiles.demo import build_voice_kwargs as _build
        return _build()

    if profile == Profile.CHINA_LANDING:
        from src.voice.profiles.china import build_voice_kwargs as _build
        return _build()

    raise ValueError(f"Unknown profile: {profile!r}")
