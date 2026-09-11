"""ASR processes load local weights only and exit before the LLM runs."""

import argparse
import json
import os
import sys
from pathlib import Path

from backend.config import Settings
from backend.pipeline.audio import AudioError
from backend.pipeline.process import run_process
from backend.schemas import Segment


def parse_whisper_cpp(data: dict) -> list[Segment]:
    result = []
    try:
        for entry in data["transcription"]:
            text = entry["text"].strip()
            if text:
                result.append(
                    Segment(
                        id=f"S{len(result) + 1}",
                        start=entry["offsets"]["from"] / 1000,
                        end=entry["offsets"]["to"] / 1000,
                        text=text,
                    )
                )
    except (KeyError, ValueError, TypeError) as exc:
        raise AudioError("ASR returned missing or invalid timestamps") from exc
    return result


def offline_env():
    return {
        **os.environ,
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "PYANNOTE_METRICS_ENABLED": "0",
    }


async def transcribe(settings: Settings, audio: Path, output: Path) -> list[Segment]:
    model = settings.asr_model_path.resolve()
    if not model.exists():
        raise AudioError(f"ASR model is missing at {model}. Download it during setup.")
    if settings.asr_backend == "whisper_cpp":
        base = output.with_suffix("")
        await run_process(
            settings.whisper_cpp_bin,
            "-m",
            str(model),
            "-f",
            str(audio),
            "-l",
            settings.asr_language,
            "-t",
            str(settings.asr_threads),
            "-oj",
            "-of",
            str(base),
            timeout=settings.stage_timeout_sec,
            env=offline_env(),
        )
        data = json.loads(output.read_text())
        result = parse_whisper_cpp(data)
        # Language here is a file-level estimate, not proof of code-switch accuracy.
        language = data.get("result", {}).get("language")
        for segment in result:
            segment.language = language
    else:
        await run_process(
            sys.executable,
            "-m",
            "backend.pipeline.asr",
            "--model",
            str(model),
            "--audio",
            str(audio),
            "--output",
            str(output),
            "--device",
            settings.asr_device,
            "--compute-type",
            settings.asr_compute_type,
            "--language",
            settings.asr_language,
            timeout=settings.stage_timeout_sec,
            env=offline_env(),
        )
        result = [Segment.model_validate(s) for s in json.loads(output.read_text())]
    output.write_text(
        json.dumps([s.model_dump() for s in result], ensure_ascii=False), encoding="utf-8"
    )
    return result


def main():
    parser = argparse.ArgumentParser()
    for key in ("model", "audio", "output", "device", "compute-type", "language"):
        parser.add_argument(f"--{key}", required=True)
    args = parser.parse_args()
    from faster_whisper import WhisperModel

    model = WhisperModel(
        args.model, device=args.device, compute_type=args.compute_type, local_files_only=True
    )
    segments, info = model.transcribe(
        args.audio,
        language=None if args.language == "auto" else args.language,
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    result = [
        Segment(
            id=f"S{i}", start=s.start, end=s.end, text=s.text.strip(), language=info.language
        ).model_dump()
        for i, s in enumerate(segments, 1)
        if s.text.strip()
    ]
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
