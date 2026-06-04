from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Profile ───────────────────────────────────────────────
    voice_profile: str = "demo"

    # ── LiveKit ───────────────────────────────────────────────
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # ── demo A/B 切换 ──────────────────────────────────────────
    # realtime: OpenAI Realtime 一体化（默认）
    # cascaded: Paraformer STT + Qwen LLM + CosyVoice TTS（阿里云三件套）
    demo_voice_mode: str = "realtime"

    # ── OpenAI（demo / realtime 模式）───────────────────────
    openai_api_key: str = ""

    # ── SIP trunk: demo / Twilio（备选）─────────────────────
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # ── SIP trunk: china_landing / 阿里云 ───────────────────
    aliyun_sip_endpoint: str = "sip.aliyuncs.com"
    aliyun_sip_access_key: str = ""
    aliyun_sip_access_secret: str = ""
    aliyun_phone_number: str = ""

    # ── china_landing LLM（OpenAI 兼容端点）─────────────────
    china_llm_base_url: str = ""
    china_llm_api_key: str = ""
    china_llm_model: str = "qwen-plus"

    # ── china_landing ASR / TTS ───────────────────────────────
    china_asr_appkey: str = ""
    china_asr_token: str = ""
    china_tts_appkey: str = ""
    china_tts_token: str = ""

    # ── DashScope（cascaded 模式：Paraformer STT + Qwen LLM + CosyVoice TTS）──
    dashscope_api_key: str = ""
    # LLM 端点：默认北京；国际版填 https://dashscope-intl.aliyuncs.com/compatible-mode/v1
    dashscope_llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_llm_model: str = "qwen-plus"
    # CosyVoice v2 音色：longcheng / longhua / longxiaochun / longnan 等
    dashscope_tts_voice: str = "longcheng"
    # 语速倍率：0.5–2.0，1.0=正常，1.1–1.2=略快利索，超 1.3 会失真
    dashscope_tts_rate: float = 1.1
    dashscope_stt_model: str = "paraformer-realtime-v2"
    # 热词表 ID（DashScope 控制台预创建）；留空则不启用
    dashscope_stt_vocabulary_id: str = ""

    # ── 数据库 ────────────────────────────────────────────────
    database_url: str = ""

    # ── 企业微信 ──────────────────────────────────────────────
    wechat_webhook_url: str = ""

    # ── Agent / SIP 路由 ──────────────────────────────────────
    agent_name: str = "visitor-agent"
    sip_room_prefix: str = "call-"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
