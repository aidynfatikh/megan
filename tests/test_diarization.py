import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from backend.config import Settings
from backend.pipeline.diarize import DiarizationError, SpeakerTurn, align_speakers, diarize
from backend.schemas import DraftReport, Segment
from backend.worker import Pipeline


def turn(start, end, speaker):
    return SpeakerTurn(start=start, end=end, speaker=speaker)


def test_alignment_preserves_text_ids_and_original_times_and_uses_arrival_order():
    segments = [
        Segment(id="S1", start=1, end=4, text="I'll prepare the draft."),
        Segment(id="S2", start=6, end=9, text="I'll review it."),
        Segment(id="S3", start=11, end=13, text="Thank you."),
    ]
    original = [s.model_dump() for s in segments]
    aligned, speakers = align_speakers(
        segments, [turn(6, 9, "raw_a"), turn(11, 13, "raw_z"), turn(1, 4, "raw_z")]
    )
    assert [s.speaker_id for s in aligned] == ["speaker_0", "speaker_1", "speaker_0"]
    assert [(s.id, s.name) for s in speakers] == [
        ("speaker_0", "Speaker 1"),
        ("speaker_1", "Speaker 2"),
    ]
    assert all(s.name_source == "anonymous" for s in speakers)
    assert [s.model_dump(exclude={"speaker_id"}) for s in aligned] == [
        s.model_dump(exclude={"speaker_id"}) for s in segments
    ]
    assert [s.model_dump() for s in segments] == original


@pytest.mark.parametrize(
    "turns",
    [
        [],
        [turn(0, 0.3, "a")],  # Too little coverage.
        [turn(0, 2, "a"), turn(2, 4, "b")],  # One ASR segment crosses a turn.
        [turn(0, 4, "a"), turn(1, 2, "b")],  # Overlapping speakers.
        [turn(0, 1.5, "a"), turn(0, 1.5, "a")],  # Duplicates cannot inflate coverage.
    ],
)
def test_ambiguous_or_weak_attribution_stays_unknown(turns):
    aligned, _ = align_speakers([Segment(id="S1", start=0, end=4, text="A statement.")], turns)
    assert aligned[0].speaker_id is None


def test_same_speaker_fragments_use_union_coverage_and_zero_duration_is_unknown():
    segments = [
        Segment(id="S1", start=0, end=4, text="A statement."),
        Segment(id="S2", start=4, end=4, text="."),
    ]
    aligned, _ = align_speakers(segments, [turn(0, 2, "a"), turn(1, 4, "a")])
    assert [s.speaker_id for s in aligned] == ["speaker_0", None]


async def test_missing_model_fails_without_starting_any_runtime(tmp_path, monkeypatch):
    run = AsyncMock()
    monkeypatch.setattr("backend.pipeline.diarize.run_process", run)
    settings = Settings(
        _env_file=None,
        diarization_backend="sortformer_nemo",
        diarization_model_path=tmp_path / "missing.nemo",
    )
    with pytest.raises(DiarizationError, match="missing"):
        await diarize(settings, tmp_path / "audio.wav", tmp_path, 4)
    run.assert_not_called()


@pytest.mark.parametrize(
    "raw",
    [
        "SPEAKER audio 1 0 5 <NA> <NA> a <NA> <NA>\n",
        "SPEAKER audio 1 nan 1 <NA> <NA> a <NA> <NA>\n",
        "not rttm\n",
    ],
)
async def test_invalid_runtime_output_is_rejected(tmp_path, monkeypatch, raw):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")

    async def run(*args, **kwargs):
        from pathlib import Path

        Path(args[args.index("--output") + 1]).write_text(raw)
        return b"", b""

    monkeypatch.setattr("backend.pipeline.diarize.run_process", run)
    settings = Settings(
        _env_file=None, diarization_backend="sortformer_cpp", diarization_model_path=model
    )
    with pytest.raises(DiarizationError):
        await diarize(settings, tmp_path / "audio.wav", tmp_path, 4)


@pytest.mark.parametrize("final_duration,accepted", [("1.909", True), ("1.910", False)])
async def test_rttm_final_frame_rounding_preserves_speakers_without_expanding_tolerance(
    tmp_path, monkeypatch, final_duration, accepted
):
    # Real 120-second recording: 118.171 + 1.909 becomes 120.08000000000001.
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")

    async def run(*args, **kwargs):
        from pathlib import Path

        if "--version" in args:
            return b"nemo-speech 0.1.0", b""
        Path(args[args.index("--output") + 1]).write_text(
            "SPEAKER audio 1 0.000 7.279 <NA> <NA> speaker_1 <NA> <NA>\n"
            f"SPEAKER audio 1 118.171 {final_duration} <NA> <NA> speaker_1 <NA> <NA>\n"
        )
        return b"", b""

    monkeypatch.setattr("backend.pipeline.diarize.run_process", run)
    settings = Settings(
        _env_file=None, diarization_backend="sortformer_cpp", diarization_model_path=model
    )
    if not accepted:
        with pytest.raises(DiarizationError):
            await diarize(settings, tmp_path / "audio.wav", tmp_path, 120)
        return
    result = await diarize(settings, tmp_path / "audio.wav", tmp_path, 120)
    assert result.turns == [turn(0, 7.279, "speaker_1"), turn(118.171, 120, "speaker_1")]
    saved = json.loads((tmp_path / "diarization.json").read_text())
    assert saved["turns"][-1]["end"] == 120


@pytest.mark.parametrize(
    "backend,suffix", [("sortformer_cpp", ".gguf"), ("sortformer_nemo", ".nemo")]
)
async def test_adapter_uses_explicit_local_model_and_offline_child(
    tmp_path, monkeypatch, backend, suffix
):
    model = tmp_path / ("model" + suffix)
    model.write_bytes(b"model")
    calls = []

    async def run(*args, **kwargs):
        from pathlib import Path

        calls.append((args, kwargs))
        if "--version" in args:
            return b"nemo-speech 0.1.0", b""
        output = Path(args[args.index("--output") + 1])
        if backend == "sortformer_cpp":
            output.write_text("SPEAKER audio 1 0 4 <NA> <NA> a <NA> <NA>\n")
        else:
            output.write_text(
                json.dumps(
                    {
                        "segments": [{"start": 0, "end": 4, "speaker": "a"}],
                        "runtime": "NeMo test / torch test",
                    }
                )
            )
        return b"", b""

    monkeypatch.setattr("backend.pipeline.diarize.run_process", run)
    settings = Settings(
        _env_file=None,
        diarization_backend=backend,
        diarization_model_path=model,
        diarization_device="cpu",
    )
    result = await diarize(settings, tmp_path / "audio.wav", tmp_path, 4)
    assert result.turns == [turn(0, 4, "a")]
    assert len(result.model_sha256) == 64
    args, kwargs = calls[0]
    assert args[args.index("--model") + 1] == str(model.resolve())
    assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
    assert kwargs["env"]["TRANSFORMERS_OFFLINE"] == "1"


@pytest.fixture
def pipeline_case(new_job, tmp_path, monkeypatch):
    from backend.pipeline.diarize import DiarizationResult

    settings = Settings(_env_file=None, diarization_backend="sortformer_nemo")
    pipeline = Pipeline(settings)
    events = []
    new_job.duration_sec = 4
    new_job.segments = [Segment(id="S1", start=0, end=4, text="I'll prepare the draft.")]
    (tmp_path / "normalized.wav").write_bytes(b"wav")

    async def unload():
        events.append("unload")

    async def separate(*args):
        events.append("diarize")
        return DiarizationResult(
            turns=[turn(0, 4, "a")], model_sha256="a" * 64, runtime="NeMo test"
        )

    async def extract(segments, language):
        events.append("extract")
        return DraftReport(
            title="Planning",
            summary=[],
            topics=[],
            decisions=[],
            open_questions=[],
            risks=[],
            action_items=[],
        )

    pipeline.ollama.unload = AsyncMock(side_effect=unload)
    pipeline.ollama.tags = AsyncMock(return_value=[])
    pipeline.ollama.extract = AsyncMock(side_effect=extract)
    monkeypatch.setattr("backend.worker.diarize", separate)
    return pipeline, events


async def test_diarization_runs_before_llm_and_is_saved_for_extraction_retry(
    pipeline_case, new_job, tmp_path
):
    pipeline, events = pipeline_case
    checkpoints = []

    async def checkpoint(stage):
        checkpoints.append((stage, new_job.model_copy(deep=True)))

    await pipeline.run(new_job, tmp_path, checkpoint)
    assert events == ["unload", "diarize", "extract"]
    assert new_job.diarization_status == "done"
    assert new_job.provenance.diarization_backend == "sortformer_nemo"
    assert new_job.provenance.diarization_model_sha256 == "a" * 64
    assert pipeline.ollama.extract.call_args.args[0][0].speaker_id == "speaker_0"
    assert next(j for stage, j in checkpoints if stage == "speakers_ready").speakers
    events.clear()
    await pipeline.run(new_job, tmp_path, checkpoint)
    assert events == ["extract"]


@pytest.mark.parametrize("failure", [RuntimeError("CUDA failure"), TimeoutError()])
async def test_diarizer_failure_keeps_report_and_unknown_speakers(
    pipeline_case, new_job, tmp_path, monkeypatch, failure
):
    pipeline, _ = pipeline_case
    monkeypatch.setattr("backend.worker.diarize", AsyncMock(side_effect=failure))
    report = await pipeline.run(new_job, tmp_path, AsyncMock())
    assert report.title == "Planning"
    assert new_job.diarization_status == "failed"
    assert not new_job.speakers
    assert new_job.segments[0].speaker_id is None
    assert any("Speaker separation failed" in w for w in new_job.warnings)


async def test_cancellation_is_not_downgraded_to_optional_failure(
    pipeline_case, new_job, tmp_path, monkeypatch
):
    pipeline, _ = pipeline_case
    monkeypatch.setattr("backend.worker.diarize", AsyncMock(side_effect=asyncio.CancelledError()))
    with pytest.raises(asyncio.CancelledError):
        await pipeline.run(new_job, tmp_path, AsyncMock())
    pipeline.ollama.extract.assert_not_called()


async def test_disabled_profile_never_starts_diarizer(
    pipeline_case, new_job, tmp_path, monkeypatch
):
    pipeline, events = pipeline_case
    pipeline.settings.diarization_backend = "none"
    separate = AsyncMock()
    monkeypatch.setattr("backend.worker.diarize", separate)
    await pipeline.run(new_job, tmp_path, AsyncMock())
    assert events == ["extract"]
    separate.assert_not_called()
    assert new_job.diarization_status == "disabled"


async def test_failed_llm_retry_preserves_completed_attribution(pipeline_case, new_job, tmp_path):
    pipeline, events = pipeline_case
    pipeline.ollama.extract.side_effect = RuntimeError("LLM failure")
    with pytest.raises(RuntimeError, match="LLM failure"):
        await pipeline.run(new_job, tmp_path, AsyncMock())
    assert new_job.diarization_status == "done"
    assert new_job.segments[0].speaker_id == "speaker_0"
    assert events == ["unload", "diarize"]


async def test_full_pipeline_finishes_asr_before_starting_sortformer(
    pipeline_case, new_job, tmp_path, monkeypatch
):
    from types import SimpleNamespace

    pipeline, events = pipeline_case
    segments = new_job.segments
    new_job.segments = []

    async def transcribe(*args):
        events.append("asr_start")
        await asyncio.sleep(0)
        events.append("asr_exited")
        return segments

    monkeypatch.setattr("backend.worker.transcribe", transcribe)
    monkeypatch.setattr(
        "backend.worker.normalize_audio",
        AsyncMock(return_value=SimpleNamespace(duration=4, silent=False)),
    )
    await pipeline.run(new_job, tmp_path, AsyncMock())
    assert events == ["unload", "asr_start", "asr_exited", "unload", "diarize", "extract"]


async def test_unload_failure_prevents_starting_another_model(pipeline_case, new_job, tmp_path):
    pipeline, events = pipeline_case
    pipeline.ollama.unload.side_effect = RuntimeError("Cannot release GPU model")
    with pytest.raises(RuntimeError, match="Cannot release"):
        await pipeline.run(new_job, tmp_path, AsyncMock())
    assert events == []


@pytest.mark.parametrize("cancel", [False, True])
async def test_timeout_or_cancellation_reaps_model_child_before_returning(tmp_path, cancel):
    import os
    import sys

    from backend.pipeline.process import run_process

    pidfile = tmp_path / "child.pid"
    script = "import os,sys,time; from pathlib import Path; Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(60)"
    task = asyncio.create_task(run_process(sys.executable, "-c", script, str(pidfile), timeout=1))
    if cancel:
        async with asyncio.timeout(3):
            while not pidfile.exists():
                await asyncio.sleep(0.01)
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else TimeoutError):
        await task
    with pytest.raises(ProcessLookupError):
        os.kill(int(pidfile.read_text()), 0)


async def test_silent_meeting_does_not_leave_optional_stage_pending(
    pipeline_case, new_job, tmp_path, monkeypatch
):
    from types import SimpleNamespace

    pipeline, events = pipeline_case
    new_job.segments = []
    new_job.diarization_status = "pending"
    monkeypatch.setattr(
        "backend.worker.normalize_audio",
        AsyncMock(return_value=SimpleNamespace(duration=4, silent=True)),
    )
    report = await pipeline.run(new_job, tmp_path, AsyncMock())
    assert report.content_status == "no_usable_speech"
    assert new_job.diarization_status == "disabled"
    assert events == []


async def test_disabling_optional_stage_before_retry_clears_stale_failed_state(
    pipeline_case, new_job, tmp_path
):
    pipeline, _ = pipeline_case
    new_job.diarization_status = "failed"
    new_job.provenance.diarization_backend = "sortformer_nemo"
    new_job.warnings = ["Speaker separation failed. Old attempt.", "Another warning."]
    pipeline.settings.diarization_backend = "none"
    await pipeline.run(new_job, tmp_path, AsyncMock())
    assert new_job.diarization_status == "disabled"
    assert new_job.provenance.diarization_backend == "none"
    assert new_job.warnings == ["Another warning."]
