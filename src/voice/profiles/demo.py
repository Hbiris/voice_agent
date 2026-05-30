import os
from typing import Any


def build_voice_kwargs() -> dict[str, Any]:
    """
    Demo 语音栈：OpenAI Realtime API 一体处理 STT+LLM+TTS，原生支持中文。
    voice 可根据 OpenAI / LiveKit 支持情况调整。
    """
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