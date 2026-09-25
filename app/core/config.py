from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

class Settings(BaseSettings):
    bot_token: str = Field(min_length=10, repr=False)
    database_url: str = Field(min_length=1, repr=False)
    owner_telegram_id: int = Field(gt=0)
    manager_telegram_id: int | None = None
    admin_invite_lifetime_hours: int = Field(default=24, ge=1, le=168)
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', case_sensitive=False, extra='ignore', hide_input_in_errors=True)

    @field_validator('manager_telegram_id', mode='before')
    @classmethod
    def empty_optional_id(cls, value):
        return None if value == '' else value

    @field_validator('database_url')
    @classmethod
    def postgres_url(cls, value):
        from sqlalchemy.engine import make_url
        url = make_url(value)
        if url.drivername != 'postgresql+asyncpg' or not url.database:
            raise ValueError('Use a postgresql+asyncpg URL with a database name')
        return value

@lru_cache
def get_settings():
    return Settings()
settings = get_settings()
