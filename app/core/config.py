from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    bot_token: str
    database_url: str
    owner_telegram_id: int
    manager_telegram_id: int | None = None
    admin_invite_lifetime_hours: int = 24
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', case_sensitive=False, extra='ignore')

@lru_cache
def get_settings():
    return Settings()
settings = get_settings()
