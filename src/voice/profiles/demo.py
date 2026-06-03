import os
from typing import Any


def build_voice_kwargs() -> dict[str, Any]:
    """根据 DEMO_VOICE_MODE 返回对应语音栈的 AgentSession kwargs。

    DEMO_VOICE_MODE=realtime  (默认): OpenAI Realtime API，一体化 STT+LLM+TTS
    DEMO_VOICE_MODE=cascaded        : 阿里云三件套 Paraformer STT + Qwen LLM + CosyVoice TTS
    """
    from src.config.settings import get_settings
    settings = get_settings()

    if settings.demo_voice_mode == "cascaded":
        return _build_cascaded(settings)

    return _build_realtime(settings)


def _build_realtime(settings) -> dict[str, Any]:
    from livekit.plugins import openai as lk_openai

    model = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-2")
    voice = os.getenv("OPENAI_REALTIME_VOICE", "marin")

    return {
        "llm": lk_openai.realtime.RealtimeModel(
            voice=voice,
            model=model,
            temperature=0.7,
        ),
    }


def _build_cascaded(settings) -> dict[str, Any]:
    """阿里云三件套：Paraformer STT + Qwen LLM（OpenAI 兼容）+ CosyVoice TTS。

    密钥优先从 DASHSCOPE_API_KEY 环境变量读取（与官方 DashScope SDK 同名），
    其次读 settings.dashscope_api_key（.env 里的 DASHSCOPE_API_KEY）。
    """
    from livekit.plugins.aliyun import STT, TTS
    from livekit.plugins import openai as lk_openai, silero

    api_key = settings.dashscope_api_key or os.environ.get("DASHSCOPE_API_KEY") or ""
    if not api_key:
        raise ValueError(
            "DASHSCOPE_API_KEY is required for cascaded mode. "
            "Set it in .env or as an environment variable."
        )

    vocabulary_id = settings.dashscope_stt_vocabulary_id or None

    return {
        "vad": silero.VAD.load(),
        "stt": STT(
            model=settings.dashscope_stt_model,
            language="zh",
            api_key=api_key,
            vocabulary_id=vocabulary_id,
            # 过滤"嗯""啊"等语气词，保持转写干净
            disfluency_removal_enabled=True,
            # 将数字词转为阿拉伯数字（"一三八"→ 138）
            inverse_text_normalization_enabled=True,
            # 延长断句容忍时间，避免来电者说号码时被截断
            max_sentence_silence=800,
        ),
        "llm": lk_openai.LLM(
            model=settings.dashscope_llm_model,
            api_key=api_key,
            base_url=settings.dashscope_llm_base_url,
        ),
        "tts": TTS(
            model="cosyvoice-v2",
            voice=settings.dashscope_tts_voice,
            api_key=api_key,
            sample_rate=24000,
        ),
        # 端点延迟微调：等待用户停顿 ≥0.5s 再截断，避免打断车牌/手机号中途停顿
        "min_endpointing_delay": 0.5,
        "max_endpointing_delay": 3.0,
    }
