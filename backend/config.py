import ipaddress
import platform
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def is_loopback(host: str | None) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host or "").is_loopback
    except ValueError:
        return False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql://megan:megan@127.0.0.1:54329/megan"
    data_dir: Path = Path("data")
    frontend_dir: Path = Path("frontend/dist")
    asr_backend: Literal["faster_whisper", "whisper_cpp"] = (
        "whisper_cpp" if platform.system() == "Darwin" else "faster_whisper"
    )
    asr_model_path: Path = (
        Path("models/ggml-large-v3-turbo.bin")
        if platform.system() == "Darwin"
        else Path("models/whisper-turbo-ct2")
    )
    asr_device: Literal["cuda", "cpu"] = "cuda"
    asr_compute_type: str = "int8_float16"
    asr_language: str = "auto"
    asr_threads: int = Field(default=4, ge=1, le=32)
    whisper_cpp_bin: str = "whisper-cli"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3.5:4b"
    llm_context: int = Field(default=16384, ge=2048, le=32768)
    llm_output_tokens: int = Field(default=3500, ge=256, le=8192)
    llm_timeout_sec: float = Field(default=300, gt=0, le=1800)
    stage_timeout_sec: float = Field(default=600, gt=0, le=3600)
    max_duration_sec: float = Field(default=1800, gt=0, le=7200)
    max_upload_mb: int = Field(default=100, ge=1, le=1000)
    # Deferred bonus: expose only the implemented profile in this release.
    diarization_backend: Literal["none"] = "none"
    enable_chat: bool = True

    @field_validator("ollama_base_url")
    @classmethod
    def local_ollama(cls, value: str):
        url = urlsplit(value)
        if (
            url.scheme != "http"
            or not is_loopback(url.hostname)
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in ("", "/")
        ):
            raise ValueError(
                "Ollama must use a loopback HTTP endpoint, such as http://127.0.0.1:11434"
            )
        return value.rstrip("/")

    @field_validator("database_url")
    @classmethod
    def local_postgres(cls, value: str):
        url = urlsplit(value)
        if (
            url.scheme not in ("postgresql", "postgres")
            or not is_loopback(url.hostname)
            or url.query
            or url.fragment
        ):
            raise ValueError("Use a local PostgreSQL connection URL without query overrides")
        return value

    @field_validator("ollama_model")
    @classmethod
    def local_model(cls, value: str):
        if "cloud" in value.casefold() or "://" in value:
            raise ValueError("Cloud model tags are disabled")
        return value
