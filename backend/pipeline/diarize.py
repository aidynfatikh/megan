"""Optional local Sortformer inference, followed by conservative time alignment.

No NeMo/Torch import in the API process. Child processes exit before Qwen starts.
The original ASR text, IDs and timestamps remain unchanged.
"""

import asyncio
import hashlib
import json
from pathlib import Path

from pydantic import Field, ValidationError, model_validator

from backend.config import Settings
from backend.pipeline.asr import offline_env
from backend.pipeline.process import ProcessError, run_process
from backend.schemas import Model, Segment, Speaker


class DiarizationError(RuntimeError):
    pass


class SpeakerTurn(Model):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    speaker: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")

    @model_validator(mode="after")
    def ordered(self):
        if self.end <= self.start:
            raise ValueError("Speaker interval must have positive duration")
        return self


class DiarizationResult(Model):
    turns: list[SpeakerTurn]
    model_sha256: str
    runtime: str


def align_speakers(segments: list[Segment], turns: list[SpeakerTurn]):
    ordered = sorted(turns, key=lambda t: (t.start, t.end, t.speaker))
    ids = {}
    for t in ordered:
        ids.setdefault(t.speaker, f"speaker_{len(ids)}")
    if len(ids) > 4:
        raise DiarizationError("This Sortformer checkpoint supports at most four speakers")
    speakers = [Speaker(id=sid, name=f"Speaker {i}") for i, sid in enumerate(ids.values(), 1)]
    aligned = []
    for segment in segments:
        matching = [t for t in ordered if t.start < segment.end and t.end > segment.start]
        voices = {t.speaker for t in matching}
        speaker_id = None
        if len(voices) == 1 and segment.end > segment.start:
            # Union length: duplicate/overlapping intervals cannot inflate coverage.
            covered, previous_end = 0.0, segment.start
            for t in matching:
                start, end = max(segment.start, t.start), min(segment.end, t.end)
                covered += max(0, end - max(start, previous_end))
                previous_end = max(previous_end, end)
            if covered / (segment.end - segment.start) >= 0.8:
                speaker_id = ids[next(iter(voices))]
        aligned.append(segment.model_copy(update={"speaker_id": speaker_id}))
    return aligned, speakers


def weight_digest(path: Path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def parse_rttm(text: str):
    turns = []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 10 or fields[0] != "SPEAKER":
            raise ValueError("Invalid RTTM speaker interval")
        start, duration = float(fields[3]), float(fields[4])
        turns.append(SpeakerTurn(start=start, end=start + duration, speaker=fields[7]))
    return turns


async def diarize(settings: Settings, audio: Path, directory: Path, duration: float):
    model = settings.diarization_model_path.resolve()
    if not model.is_file() or not model.stat().st_size:
        raise DiarizationError("Sortformer model is missing. Download it during setup.")
    if settings.diarization_backend == "none":
        raise DiarizationError("Speaker separation is disabled")
    nemo = settings.diarization_backend == "sortformer_nemo"
    if model.suffix != (".nemo" if nemo else ".gguf"):
        raise DiarizationError("Sortformer model format does not match its configured runtime")
    if nemo and settings.diarization_device == "metal":
        raise DiarizationError("Use the C++ Sortformer runtime for Metal")
    output = directory / ("diarization.raw.json" if nemo else "diarization.raw.rttm")
    output.unlink(missing_ok=True)  # A failed retry cannot reuse a stale output file.
    digest = await asyncio.to_thread(weight_digest, model)
    args = (
        [
            settings.diarization_python,
            str(Path(__file__).resolve().parents[2] / "scripts" / "run_sortformer_nemo.py"),
        ]
        if nemo
        else [settings.nemo_speech_bin, "diarize"]
    )
    if nemo:
        args += ["--audio", str(audio.resolve())]
    else:
        args += [str(audio.resolve()), "--format", "rttm"]
    args += [
        "--model",
        str(model),
        "--output",
        str(output.resolve()),
        "--device",
        settings.diarization_device,
    ]
    try:
        await run_process(*args, timeout=settings.stage_timeout_sec, env=offline_env())
        if nemo:
            data = json.loads(output.read_text())
            turns = [SpeakerTurn.model_validate(t) for t in data["segments"]]
            runtime = str(data["runtime"])
        else:
            turns = parse_rttm(output.read_text())
            version, _ = await run_process(
                settings.nemo_speech_bin, "--version", timeout=10, env=offline_env()
            )
            runtime = version.decode(errors="replace").strip()[:200] or "NeMo-Speech.cpp"
        if len({t.speaker for t in turns}) > 4:
            raise ValueError("More than four speakers returned")
        for t in turns:
            # RTTM start + duration can round just above the allowed final frame.
            if t.end > duration + 0.08 + 1e-9 or t.start >= duration:
                raise ValueError("Speaker timestamps extend beyond the recording")
            t.end = min(t.end, duration)
        result = DiarizationResult(turns=turns, model_sha256=digest, runtime=runtime)
        (directory / "diarization.json").write_text(result.model_dump_json(indent=2))
        return result
    except (ProcessError, OSError, ValueError, KeyError, TypeError, ValidationError) as exc:
        raise DiarizationError("Sortformer could not produce valid speaker intervals") from exc
