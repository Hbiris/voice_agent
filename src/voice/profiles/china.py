from typing import Any


def build_voice_kwargs() -> dict[str, Any]:
    """
    国内落地语音栈：三件套分离（STT / LLM / TTS），均使用国内合规 provider。

    接入步骤（落地时替换此函数）：
    1. STT  → 安装对应 livekit plugin，例如阿里云 ASR 或讯飞 plugin，替换下方 stt=
    2. LLM  → 已走 OpenAI 兼容端点（Qwen/DeepSeek/GLM），只需填 CHINA_LLM_* 环境变量
    3. TTS  → 安装 Qwen3-TTS plugin 或其他，替换下方 tts=

    阿里云 SIP trunk 配置见 src/telephony/trunks/aliyun.md
    """
    from src.config.settings import get_settings

    settings = get_settings()

    # TODO: replace with real domestic provider plugins
    # from livekit.plugins import <china_asr_plugin>
    # from livekit.plugins import <china_tts_plugin>
    from livekit.plugins import openai as lk_openai

    return {
        # STT: 替换为国内 ASR plugin 实例
        # "stt": <ChinaASR>(appkey=settings.china_asr_appkey, token=settings.china_asr_token),
        "llm": lk_openai.LLM(
            model=settings.china_llm_model,
            base_url=settings.china_llm_base_url or None,
            api_key=settings.china_llm_api_key or None,
        ),
        # TTS: 替换为 Qwen3-TTS plugin 实例
        # "tts": <ChinaTTS>(appkey=settings.china_tts_appkey, token=settings.china_tts_token),
    }
