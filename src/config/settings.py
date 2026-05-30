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

    # ── OpenAI（demo profile）────────────────────────────────
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
