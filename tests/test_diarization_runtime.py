from unittest.mock import AsyncMock

from backend.config import Settings
from backend.runtime import diarization_available


async def test_disabled_diarization_does_not_probe_or_import_nemo(monkeypatch):
    run = AsyncMock()
    monkeypatch.setattr("backend.runtime.run_process", run)
    assert await diarization_available(Settings(_env_file=None))
    run.assert_not_called()


async def test_missing_optional_model_is_visible_in_readiness(tmp_path, monkeypatch):
    run = AsyncMock()
    monkeypatch.setattr("backend.runtime.run_process", run)
    assert not await diarization_available(
        Settings(
            _env_file=None,
            diarization_backend="sortformer_nemo",
            diarization_model_path=tmp_path / "missing.nemo",
        )
    )
    run.assert_not_called()


async def test_existing_nemo_environment_is_probed_without_loading_the_model(tmp_path, monkeypatch):
    model = tmp_path / "model.nemo"
    model.write_bytes(b"local model")
    run = AsyncMock(return_value=(b"", b""))
    monkeypatch.setattr("backend.runtime.run_process", run)
    settings = Settings(
        _env_file=None,
        diarization_backend="sortformer_nemo",
        diarization_model_path=model,
        diarization_python="/teammate/env/bin/python",
    )
    assert await diarization_available(settings)
    args = run.call_args.args
    assert args[0] == "/teammate/env/bin/python"
    assert "restore_from" not in args[-1]
    assert "find_spec" in args[-1]
    run.side_effect = RuntimeError("Environment missing")
    assert not await diarization_available(settings)
