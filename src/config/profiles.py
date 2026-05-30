from enum import Enum


class Profile(str, Enum):
    DEMO = "demo"
    CHINA_LANDING = "china_landing"


def get_profile() -> Profile:
    from src.config.settings import get_settings
    return Profile(get_settings().voice_profile)
