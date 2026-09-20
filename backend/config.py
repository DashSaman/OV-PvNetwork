import os
from pydantic_settings import BaseSettings
from typing import Optional
from fastapi import Request


class Setting(BaseSettings):
    ADMIN_USERNAME: str
    ADMIN_PASSWORD_HASH: str
    ADMIN_PASSWORD: Optional[str] = None  # legacy input only; never used for authentication
    MAIN_ADMIN_AUTH_GENERATION: str = "legacy"
    URLPATH: str = "dashboard"
    VITE_URLPATH: str = "dashboard"
    HOST: str = "127.0.0.1"
    PORT: int = 9000
    DEBUG: str = "WARNING"
    DOC: bool = False
    SSL_KEYFILE: Optional[str] = None
    SSL_CERTFILE: Optional[str] = None
    JWT_SECRET_KEY: str
    MIRZA_API_KEY: Optional[str] = None
    DATABASE_URL: Optional[str] = None
    JWT_ACCESS_TOKEN_EXPIRES: int = 86400  # in seconds
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10
    SUBSCRIPTION_URL_PREFIX: Optional[str] = None
    SUBSCRIPTION_PATH: str = "sub"
    CORS_ORIGINS: str = ""

    class Config:
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")


config = Setting()
