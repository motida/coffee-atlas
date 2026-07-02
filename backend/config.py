"""Centralized application settings loaded from environment variables."""

from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    DUCKDB_PATH: str = "./data/coffee_atlas.duckdb"

    # Postgres (user data store). Empty disables the user/account features.
    DATABASE_URL: str = ""

    # Auth (custom JWT-in-cookie). JWT_SECRET must be set for auth to work.
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_TTL_MINUTES: int = 10080  # 7 days
    COOKIE_NAME: str = "ca_session"
    COOKIE_SECURE: bool = True  # set False for local http dev
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"

    GEMINI_API_KEY: str = ""

    ENABLE_EMBEDDINGS: bool = True


settings = Settings()
