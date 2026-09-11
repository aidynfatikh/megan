import pytest
from pydantic import ValidationError

from backend.config import Settings


@pytest.mark.parametrize(
    "url",
    [
        "https://ollama.com",
        "http://192.168.1.10:11434",
        "http://localhost.evil.test",
        "http://127.0.0.1@external.test",
    ],
)
def test_llm_endpoint_cannot_send_meetings_off_device(url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ollama_base_url=url)


def test_cloud_model_tags_and_nonpostgres_databases_are_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ollama_model="qwen3.5:cloud")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="sqlite:///test.db")


def test_local_services_are_valid():
    settings = Settings(
        _env_file=None,
        ollama_base_url="http://127.0.0.1:11435",
        database_url="postgresql://megan@localhost:54329/megan",
    )
    assert settings.ollama_base_url == "http://127.0.0.1:11435"


def test_preflight_requires_the_pinned_report_tokenizer(tmp_path):
    """Without it, prompt length silently reverts to a strict byte count."""
    from backend.config import Settings
    from backend.runtime import tokenizer_available

    missing = Settings(
        _env_file=None, ollama_model="qwen3.5:4b", llm_tokenizer_path=tmp_path / "absent.json"
    )
    present = tmp_path / "tokenizer.json"
    present.write_text("{}", encoding="utf-8")

    assert not tokenizer_available(missing)
    assert tokenizer_available(
        Settings(_env_file=None, ollama_model="qwen3.5:4b", llm_tokenizer_path=present)
    )
    # Another model family uses the byte fallback by design, so the file is not required.
    assert tokenizer_available(
        Settings(
            _env_file=None, ollama_model="qwen3:8b", llm_tokenizer_path=tmp_path / "absent.json"
        )
    )
