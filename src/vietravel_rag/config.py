"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings for model access and local storage."""

    deepseek_api_key: str
    gemini_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-flash"
    embedding_model: str = "gemini-embedding-001"
    embedding_output_dimensionality: int = 768
    chroma_persist_dir: str = "chroma_db"
    tour_resolution_relevance_floor: float = 0.65
    tour_resolution_margin: float = 0.3

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
