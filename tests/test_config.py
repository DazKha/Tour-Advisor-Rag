from vietravel_rag.config import Settings


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test")

    settings = Settings()

    assert settings.llm_model == "deepseek-flash"
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert settings.chroma_persist_dir == "chroma_db"
