import asyncio
import math
import struct
import wave

import pytest

from backend.pipeline.asr import parse_whisper_cpp
from backend.pipeline.audio import AudioError, normalize_audio


@pytest.fixture
def wav_file(tmp_path):
    path = tmp_path / "input.wav"
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(44100)
        frame = b"".join(
            struct.pack("<hh", int(1000 * math.sin(i / 10)), int(1000 * math.sin(i / 10)))
            for i in range(44100)
        )
        audio.writeframes(frame)
    return path


@pytest.mark.parametrize("suffix", ["wav", "mp3", "m4a"])
async def test_real_ffmpeg_decodes_all_required_formats(tmp_path, wav_file, suffix):
    source = wav_file
    if suffix != "wav":
        source = tmp_path / f"input.{suffix}"
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-v", "error", "-y", "-i", str(wav_file), str(source)
        )
        assert await proc.wait() == 0
    target = tmp_path / "normalized.wav"
    info = await normalize_audio(source, target, max_duration=10, timeout=10)
    assert info.duration == pytest.approx(1, abs=0.1)
    with wave.open(str(target)) as audio:
        assert audio.getframerate() == 16000
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2


async def test_invalid_or_overlong_audio_is_rejected(tmp_path, wav_file):
    bad = tmp_path / "bad.mp3"
    bad.write_text("this is not an audio file")
    with pytest.raises(AudioError, match="decode|audio"):
        await normalize_audio(bad, tmp_path / "bad.wav", max_duration=10, timeout=10)
    with pytest.raises(AudioError, match="duration|limit"):
        await normalize_audio(wav_file, tmp_path / "long.wav", max_duration=0.5, timeout=10)


def test_whisper_cpp_offsets_are_milliseconds_not_seconds():
    data = {"transcription": [{"offsets": {"from": 1250, "to": 4500}, "text": " Сәлем! "}]}
    segments = parse_whisper_cpp(data)
    assert segments[0].start == 1.25
    assert segments[0].end == 4.5
    assert segments[0].text == "Сәлем!"


def test_whisper_cpp_does_not_accept_missing_or_invalid_timestamps():
    with pytest.raises(AudioError):
        parse_whisper_cpp({"transcription": [{"text": "Hi"}]})
