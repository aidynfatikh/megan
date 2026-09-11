# Optional Sortformer speaker separation

The core profile runs Whisper → Qwen. Enabling Sortformer runs **Whisper → Sortformer → Qwen**, with each audio model in a separate process that exits before the next model starts. The same scheduler also serializes chat. Sortformer runs on the original normalized 16 kHz mono recording; it never transcribes concatenated speaker clips.

Two adapters use the same Sortformer v2 checkpoint:

| Setting | Runtime / artifact | Intended machine |
|---|---|---|
| `DIARIZATION_BACKEND=none` | No diarizer or additional dependency | Default on fresh installs |
| `DIARIZATION_BACKEND=sortformer_nemo` | NeMo/PyTorch and a local `.nemo` checkpoint | Fatikh's preserved Linux/CUDA environment |
| `DIARIZATION_BACKEND=sortformer_cpp` | NVIDIA NeMo-Speech.cpp and a local Q8 GGUF | Mac with Metal; other runtime builds require testing |

The NeMo adapter follows Fatikh's `diarize_local.py` loading and streaming configuration, but uses one recording per child process, never downloads during a job, and omits audio cutting. His original scripts are preserved separately. `concat_speakers.py` and `transcribe_local.py` are not part of this pipeline.

## Mac setup

With the base app already installed, run this **while online**, from the repository root:

```bash
.venv/bin/python scripts/setup_diarization.py --runtime cpp --install-mac-runtime
```

This verifies/downloads the approximately 147 MB GGUF and installs NVIDIA's pinned **NeMo-Speech.cpp 0.1.0** Apple Silicon Metal archive under `.local/nemo-speech/`. It verifies both SHA-256 checksums. No Homebrew or Python inference dependencies are added.

Set these entries in `.env` and restart the API:

```dotenv
DIARIZATION_BACKEND=sortformer_cpp
DIARIZATION_MODEL_PATH=models/diar_streaming_sortformer_4spk-v2.q8_0.gguf
NEMO_SPEECH_BIN=.local/nemo-speech/bin/nemo-speech
DIARIZATION_DEVICE=metal
```

Use `DIARIZATION_DEVICE=cpu` only after measuring that profile. It is not the tested Mac demo profile.

## Fatikh's NeMo setup

Keep the existing NeMo/PyTorch environment separate from Megan's `.venv`. Set `DIARIZATION_PYTHON` to its actual Python executable; copying a virtual environment directory from another OS is not supported.

If the existing model file is available, point `DIARIZATION_MODEL_PATH` to it. Otherwise, download our pinned `.nemo` while online:

```bash
.venv/bin/python scripts/setup_diarization.py --runtime nemo
```

Example settings; replace the interpreter path with the real one:

```dotenv
DIARIZATION_BACKEND=sortformer_nemo
DIARIZATION_MODEL_PATH=models/diar_streaming_sortformer_4spk-v2.nemo
DIARIZATION_PYTHON=/absolute/path/to/nemo-environment/bin/python
DIARIZATION_DEVICE=cuda
```

The historical `/home/fatikh/models/diar_streaming_sortformer_4spk-v2.nemo` can be used directly if present. The historical `/home/fatikh/ML/ML` environment and driver compatibility still need checking on his machine. No NeMo installation on that laptop is claimed by this repository.

The child runs `restore_from()` on the explicit local checkpoint, then `model.to(device).eval()` under `torch.inference_mode()`. It retains Fatikh's `chunk_len=124`, `chunk_right_context=1`, `fifo_len=124`, `spkcache_update_period=124`, `spkcache_len=188`, and uses `batch_size=1`. Those settings are not a laptop memory or speed guarantee.

## Launch and check

```bash
.venv/bin/megan preflight
bash scripts/run_local.sh --port 8765
# Another terminal:
.venv/bin/megan process /path/to/two-speaker-meeting.wav \
  --date 2026-09-11 --language ru --api http://127.0.0.1:8765 \
  --output .local/speaker-report.json
```

Preflight and System status show optional diarization availability. They do not load the model or establish GPU compatibility. A missing optional runtime does not prevent core reports. Switch back to `DIARIZATION_BACKEND=none` and restart to use the two-model profile.

## Output, attribution and failure behavior

- Speaker IDs are assigned in order of first appearance and remain stable within the meeting. Display names start as `Speaker 1`, `Speaker 2`, etc. They are not inferred personal identities.
- Only voices that hold at least one attributed segment are listed as speakers. A voice can end up holding nothing: a sub-second false alarm inside a silent gap intersects no ASR segment, and a voice heard only underneath another stays unattributed. Listing such a name would claim a participant the transcript cannot show, and it could be neither filtered nor checked against the audio. A single-speaker recording therefore lists one voice, not two.
- A transcript segment receives a label only when **exactly one voice** intersects it and the union of that voice's intervals covers at least **50%** of the segment. Where a single voice is present the uncovered remainder is silence, not another speaker, so no competing claim exists on the text. Overlap, speaker changes within an ASR segment, very brief contact with a voice, and zero-duration segments remain unknown. This threshold is a conservative alignment rule, not a confidence score.
- Segments touched by **two or more voices are never attributed**, whatever the dominant share. Without word-level timestamps their text cannot be split, so choosing a dominant speaker would assign one participant's words to another. Measured against real Sortformer turns on five Russian/Kazakh recordings, this remaining case is the large majority of unknown attribution; raising coverage above 50% for single-voice segments only discarded usable labels.
- Original ASR text, segment IDs, and timestamps stay unchanged. Segment-level timing can lose attribution on short or mixed turns; word-level alignment is not implemented.
- Self-assigned tasks can reference an anonymous speaker only with matching owner quotations, matching speaker labels, and first-person wording. If Qwen emits a generic speaker name or omits the ID, the reference can be recovered from the quoted segment's voice, never from its guessed speaker number. These assignments remain marked for review. Named assignments such as “Alex will send it” do not establish that the current voice is Alex.
- The Transcript tab lists each voice as a filter: selecting one or more shows only their segments, and selecting none shows the whole transcript. Unattributed passages belong to no voice, so a filter hides them. Renaming is no longer offered in the interface; `PATCH /api/jobs/{id}/speakers/{speaker_id}` still accepts a display name, and linked self-assignments update as user edits while explicit assignments to other named people remain independent. JSON, CSV, and ICS preserve the displayed owner; CSV also exports the speaker ID.
- `diarization_status` distinguishes disabled, pending, running, done, and failed. Jobs record the chosen backend, model filename, actual weight SHA-256, and runtime version. Raw speaker intervals are saved under the job directory as `diarization.json`; the database contains the attributed transcript and speaker names.
- A missing model, runtime error, invalid output, or timeout produces a visible warning and continues report generation with unknown speakers. A process cancellation still interrupts the job. Failure to unload the previous GPU model stops the pipeline before another model starts.
- Completed attribution is persisted before extraction, so an LLM retry reuses it. Retrying an interrupted/failed job can rerun an incomplete diarization stage. Changing the setting does not relabel completed reports; upload again to reprocess with a different profile.

## Limits and acceptance

This checkpoint supports at most **four voices**. It does not reliably detect that a recording contains more than four people. NVIDIA documents possible degradation for non-English speech, noise, and very long recordings. The C++ Q8 and NeMo checkpoints are different weight formats/precision, so their outputs and timing can differ.

Review real Russian, Kazakh, English, and mixed meetings on the RTX machine. Check overlapping speech, short acknowledgments, recurring voices, named nonparticipants, first-person commitments, and silence. Measure peak VRAM/RAM and consecutive jobs. Repeat the whole app test with external networking disabled; the C++ adapter always supplies an existing absolute local path, and the NeMo child forces Hugging Face offline mode.

See [VERIFICATION.md](VERIFICATION.md) for observed results. Test doubles establish orchestration and failure behavior; they do not establish NeMo/CUDA inference quality.

Sources: [NVIDIA Sortformer v2 model card](https://huggingface.co/nvidia/diar_streaming_sortformer_4spk-v2), [NeMo-Speech.cpp CLI](https://github.com/NVIDIA/NeMo-Speech.cpp/blob/v0.1.0/docs/cli.md), [runtime release](https://github.com/NVIDIA/NeMo-Speech.cpp/releases/tag/v0.1.0). Artifact revisions and checksums are pinned in [model_manifest.json](../scripts/model_manifest.json).
