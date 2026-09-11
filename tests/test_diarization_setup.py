import hashlib

import pytest

from scripts.setup_diarization import ensure_file


def test_check_only_never_downloads_a_missing_weight(tmp_path, respx_mock):
    with pytest.raises(ValueError, match="missing|checksum"):
        ensure_file(tmp_path / "model.gguf", "https://example.test/model", "a" * 64, check=True)
    assert not respx_mock.calls


def test_corrupt_download_is_not_promoted_or_used(tmp_path, respx_mock):
    url = "https://example.test/model"
    respx_mock.get(url).respond(200, content=b"wrong model")
    target = tmp_path / "model.gguf"
    target.write_bytes(b"existing model")
    with pytest.raises(ValueError, match="checksum"):
        ensure_file(target, url, "a" * 64)
    assert target.read_bytes() == b"existing model"


def test_pinned_download_is_verified_and_then_reused_offline(tmp_path, respx_mock):
    data = b"pinned model"
    digest = hashlib.sha256(data).hexdigest()
    url = "https://example.test/model"
    route = respx_mock.get(url).respond(200, content=data)
    target = tmp_path / "model.gguf"
    ensure_file(target, url, digest)
    ensure_file(target, url, digest, check=True)
    assert target.read_bytes() == data
    assert route.call_count == 1
