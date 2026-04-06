"""Centralized application settings loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    DUCKDB_PATH: str = "./data/coffee_atlas.duckdb"

    OPENAI_API_KEY: str = ""
    MAPBOX_ACCESS_TOKEN: str = ""
    GOOGLE_PLACES_API_KEY: str = ""

    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 3000

    ENABLE_EMBEDDINGS: bool = True
    ENABLE_GRAPH: bool = True


settings = Settings()
