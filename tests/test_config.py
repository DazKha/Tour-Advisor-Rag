from pathlib import Path

from vietravel_rag.config import Settings


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test")

    settings = Settings(_env_file=None)

    assert settings.llm_model == "deepseek-flash"
    assert settings.embedding_model == "gemini-embedding-001"
    assert settings.embedding_output_dimensionality == 768
    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert settings.chroma_persist_dir == "chroma_db"


def test_settings_loads_dotenv_and_environment_overrides_it(tmp_path: Path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DEEPSEEK_API_KEY=deepseek-from-file\n"
        "GEMINI_API_KEY=gemini-from-file\n"
        "LLM_MODEL=file-model\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LLM_MODEL", "environment-model")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    settings = Settings()

    assert settings.deepseek_api_key == "deepseek-from-file"
    assert settings.gemini_api_key == "gemini-from-file"
    assert settings.llm_model == "environment-model"
