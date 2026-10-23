"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings for model access and local storage."""

    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-flash"
    openai_api_key: str
    embedding_model: str = "text-embedding-3-small"
    chroma_persist_dir: str = "chroma_db"
    tour_resolution_relevance_floor: float = 0.65
    tour_resolution_margin: float = 0.3

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
