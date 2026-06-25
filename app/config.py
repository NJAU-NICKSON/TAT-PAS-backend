from functools import lru_cache
from typing import Union
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    MONGO_URI: str  
    MONGO_DB: str = "tatpas"
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALLOWED_ORIGINS: Union[list[str], str] = ["http://localhost:5173"]
    ENVIRONMENT: str = "development"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # accept a comma-separated string for origins
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
# cached so we build it once
@lru_cache()
def get_settings() -> Settings:
    return Settings()
