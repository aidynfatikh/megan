import asyncio
import json
import math
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path

from backend.pipeline.process import ProcessError, run_process


class AudioError(RuntimeError):
    pass


@dataclass
class AudioInfo:
    duration: float
    silent: bool


def inspect_wav(path: Path):
    with wave.open(str(path)) as audio:
        duration = audio.getnframes() / audio.getframerate()
        # Only exact/near digital silence is filtered. Quiet speech is kept.
        while frames := audio.readframes(16000):
            if any(abs(v) >= 4 for v in array("h", frames)):
                return AudioInfo(duration=duration, silent=False)
    return AudioInfo(duration=duration, silent=True)


async def normalize_audio(
    source: Path, destination: Path, *, max_duration: float, timeout: float
) -> AudioInfo:
    try:
        out, _ = await run_process(
            "ffprobe",
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-show_entries",
            "format=duration,format_name",
            "-of",
            "json",
            str(source),
            timeout=20,
        )
        info = json.loads(out)["format"]
        duration = float(info.get("duration", 0))
        if not math.isfinite(duration) or duration <= 0:
            raise AudioError("Cannot determine the audio duration.")
        if duration > max_duration:
            raise AudioError(f"Recording exceeds the {max_duration:g}-second duration limit.")
        if not set(info.get("format_name", "").split(",")) & {"mp3", "wav", "mov", "mp4", "m4a"}:
            raise AudioError("Unsupported audio format. Use MP3, WAV, or M4A.")
        await run_process(
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            str(source),
            "-map",
            "0:a:0",
            "-vn",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            "-t",
            str(max_duration + 1),
            str(destination),
            timeout=timeout,
        )
        decoded = await asyncio.to_thread(inspect_wav, destination)
        if decoded.duration > max_duration + 0.1:
            raise AudioError("Decoded audio exceeds the duration limit.")
        return decoded
    except (ProcessError, KeyError, ValueError, wave.Error) as exc:
        raise AudioError(
            "Cannot decode this audio. Check the file and ffmpeg installation."
        ) from exc
