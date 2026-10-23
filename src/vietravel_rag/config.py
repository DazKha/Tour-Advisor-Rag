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

    model_config = SettingsConfigDict(env_file=None, extra="ignore")
