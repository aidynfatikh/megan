# Megan — AI Meeting Intelligence

**AI Steppe Tech Hack · Track 01 · Astana, Alem.ai · 8 hours → pitch + live demo**

---

## 1. Context

`docs/TZ_AI_Meeting_Intelligence.pdf` and `docs/AI_Steppe_Tech_Hack_Tasks.pptx` define the task: a **100% offline** service that ingests a meeting audio file (MP3/WAV/M4A) and produces a structured protocol — executive summary, decisions, topics, open questions, action items — exportable to CSV/JSON/PDF. Bonuses: speaker diarization, RU/KZ/EN multilingual and code-switched speech, RAG chat over the meeting, task-tracker integration, risk/blocker detection.

Three facts from the deck drive every decision in this document:

- **8 hours of development**, then pitching and Live Demo.
- On demo day **the jury supplies a random audio file** — we cannot tune to known input.
- **Processing speed of a 2-minute recording is explicitly scored.**

### Scoring (100 points)

| Block | Criterion | Max |
|---|---|---|
| Обязательный | Функциональность — transcription, summary, decisions, task table, export | 30 |
| Обязательный | Точность ИИ — correct assignees, deadlines, **no hallucinations** | 20 |
| Обязательный | **100% локальность** — zero requests to external commercial APIs | 20 |
| Бонусный | Фичи — diarization, RAG chat, multilingual, integrations | 15 |
| Бонусный | UI/UX и производительность — speed on a 2-min recording | 10 |
| Бонусный | Презентация — quality of the live demo | 5 |

**Read the scoring honestly:** 50 of the 100 points are *locality* and *accuracy*, not features. The plan below spends disproportionate effort on grounding/verification and on provable offline operation, because that is where the points are.

**Team:** 2 developers. **Dev A** = AI pipeline. **Dev B** = backend API + frontend.

---

## 2. Hardware and the VRAM budget

RTX 4060 Laptop — **8188 MiB VRAM**, 15 GB system RAM, 16 CPU cores, driver 575.51.03 / CUDA 12.9. Disk is being freed by the user, so **model size is not a constraint; VRAM and wall-clock are.**

The three model families cannot be co-resident. The pipeline runs **stages strictly sequentially with explicit unload** between them (`del model; torch.cuda.empty_cache()`). A reload from page cache costs 2-4 s and is far cheaper than an OOM in front of the jury.

| Stage | Model | VRAM | Notes |
|---|---|---|---|
| 1. Decode | ffmpeg → 16 kHz mono PCM | 0 | CPU |
| 2. Diarize | pyannote community-1 | ~1.5 GB | unlimited speakers; load → run → unload |
| 2b. Diarize (fast/fallback) | Sortformer streaming 4spk v2 | ~0.6 GB | ~10x faster, capped at 4 speakers |
| 3. ASR | faster-whisper large-v3-turbo (fp16) | ~1.8 GB | load → run → unload |
| 3b. KZ re-decode | kazakh-whisper-large-v3-turbo | ~1.8 GB | swaps into the same slot |
| 4. Structure | Qwen3.5-9B Q4 via Ollama | ~5.0 GB | separate process, `keep_alive` managed |
| 5. Embed (RAG) | multilingual-e5-small | 0 | **CPU on purpose** — ~2 s per meeting, keeps VRAM free |

**Peak VRAM at any instant ≈ 5.0-5.5 GB.** The headroom is deliberate: the demo machine is also driving a display, and Ollama's KV cache grows with context.

**VRAM discipline rules:**
- Ollama gets `keep_alive: 0` posted before any audio stage of the *next* job begins, so it releases VRAM.
- The worker holds one `asyncio.Semaphore(1)` around all GPU work.
- Never load an ASR model while a diarizer is resident — the stage machine enforces the order.

### Performance target

**A 2-minute recording must complete in under 45 s end-to-end**: ~5 s diarize (incl. load), ~6 s ASR, ~25 s LLM, rest overhead. "Fast mode" (`qwen3.5:4b` + Sortformer) targets ~25 s.

This is a scored criterion — **measure it with a stopwatch in the code, don't estimate it**, and put the real number on a slide.

---

## 3. What already exists on this machine — do not rebuild

| Asset | Detail |
|---|---|
| `/home/fatikh/models/diar_streaming_sortformer_4spk-v2.nemo` | **450 MB, complete.** Load by path via `NEMO_MODEL_PATH`. The HF cache copy is a corrupt `.incomplete` blob — ignore it. |
| `/home/fatikh/ML/ML` | Python 3.12 venv, **torch 2.11.0+cu129 with CUDA working**, **`nemo_toolkit 2.7.0` imports cleanly**, plus transformers 4.57, sentence-transformers, librosa, soundfile, openai-whisper, vllm 0.21. |
| `/home/fatikh/issai/audio-test/diarize_local.py` | Working Sortformer harness — port the useful parts (below). |
| `/home/fatikh/issai/audio-test/concat_speakers.py` | Span-merge + numpy slicing, avoids a known ffmpeg `atrim` OOM on long files. |
| `/home/fatikh/issai/audios/*.mp3` | **5 long RU/KZ podcast-style recordings** with existing Sortformer output in `audios_diarization/jsons/`. Our test corpus. |

**Reuse `~/ML/ML` rather than building a fresh venv.** A NeMo install from scratch is the single most fragile thing we could attempt inside an 8-hour window, and this venv already has a working one. Snapshot before touching it:

```bash
source ~/ML/ML/bin/activate
uv pip freeze > ~/ML/ML-requirements.backup.lock
```

Only additions needed: `pyannote.audio`, `faster-whisper`, `ctranslate2`, `rapidfuzz`, `fastapi`, `uvicorn`, `weasyprint`, `ics`.

### What to port from `diarize_local.py`

- The `load_model()` + **tuned streaming-preset block**: `chunk_len=124, chunk_right_context=1, fifo_len=124, spkcache_update_period=124, spkcache_len=188` (the "high latency / RTF 0.005" preset). The file also documents presets for very-high, 1.04 s low-latency and 0.32 s ultra-low — hard-won tuning, keep the table.
- `_parse_segments()` — NeMo returns `"start end speaker"` strings.
- The 16 kHz mono loader (soundfile + librosa resample).
- Its output contract `{"data": {"segments": [{"start", "end", "speaker"}]}}` — we keep this shape.

From `concat_speakers.py`: the merge constants `MERGE_GAP = 0.2`, `MIN_SEG_DUR = 0.2`. Sortformer emits 0.16 s-granularity segments including spurious sub-0.2 s ones; this cleans them. Applies equally to pyannote output.

### Not installed — must be added

Ollama (**absent entirely**), `pyannote.audio` (note: `pyannote.core`/`.database`/`.metrics` are present but **not** `.audio`), faster-whisper, ctranslate2, **any LLM weights**, **any Whisper weights**.

### Explicitly ignore

`issai/audio-test/diarize.py` and `transcribe.py` call the remote Mangisõz API (`mangisoz.nu.edu.kz`). **Using them would be disqualifying** on the 20-point locality criterion. Do not copy them into this repo at all.

---

## 4. Model stack

| Role | Choice | Rationale |
|---|---|---|
| Diarization (primary) | `pyannote/speaker-diarization-community-1` | Lowest published DER (~11.2 VoxConverse / ~11.7 AliMeeting-4), **unlimited speakers**, language-agnostic. ~4 lines to integrate. |
| Diarization (fallback / fast) | `nvidia/diar_streaming_sortformer_4spk-v2` | Already on disk, no gating, RTF ~0.005. Insurance + "fast mode". Capped at 4 speakers. |
| ASR (RU/EN) | `openai/whisper-large-v3-turbo` → CT2 | ~4x faster than large-v3, near-identical Russian quality. Speed is scored. |
| ASR (KZ) | `shyngys879/kazakh-whisper-large-v3-turbo` → CT2 | ~1,500 h Kazakh fine-tune, strongest open KZ ASR. **Same architecture → same runtime, just swap weights.** |
| LLM | `qwen3.5:9b` Q4 via **Ollama** | Released Mar 2026. ~5 GB at Q4, 201 languages, large reasoning jump (GPQA-D 81.7). |
| LLM (fast mode) | `qwen3.5:4b` | ~2x tok/s for the speed demo. |
| Embeddings | `intfloat/multilingual-e5-small` (CPU) | 471 MB, RU/KZ capable, zero VRAM. |

### Model currency — verified Sept 2026, not assumed

Sources are partly vendor/SEO blogs. **Confirm each with a real pull and a real run at hour 0**, and keep the previous generation one env var away.

- **Qwen3.5 shipped its small tier on 2 Mar 2026** (9B/4B/2B/0.8B). The 9B is the new default for 8 GB cards. Adopt; keep `qwen3:8b` as the fallback tag.
- **Turn thinking mode off for extraction.** This is an extraction task, not a reasoning task — thinking tokens are pure latency against a scored clock. A/B on one meeting before committing.
- **Nothing has displaced Whisper for our language mix.** The Open ASR Leaderboard leader (Canary-Qwen-2.5B, 5.63% WER) and the speed leader (Parakeet-TDT, RTFx >2000) are **English-only models on English-only benchmarks** — irrelevant to Kazakh.
- **Quality/Fast toggle on ASR:** turbo (~6 s per 2-min clip) vs full `large-v3` (~24 s, better multilingual WER). Same CT2 runtime, one env var.

---

## 5. Decision log

Every significant fork, with the reason. Written down so neither dev relitigates it at hour 5.

| # | Decision | Rejected alternative | Why |
|---|---|---|---|
| D1 | FastAPI + SQLite + in-process asyncio worker | **Kafka + worker fleet** | One 8 GB GPU serializes everything; queue depth is always 1. Kafka buys throughput we cannot use and costs ~1.5-2 h of the 8. `Semaphore(1)` is an honest model of the hardware. |
| D2 | **Ollama** for LLM serving | **vLLM** (already installed) | vLLM preallocates VRAM via `gpu_memory_utilization`, ~60 s startup, weak GGUF support. Its advantage is batched serving for many concurrent users — we have one. Ollama swaps models, unloads on demand, and the TZ names it explicitly. |
| D3 | **pyannote community-1** as primary diarizer | **Sortformer as primary** | Sortformer is hard-capped at 4 speakers (see §6). The jury hands us an unknown file. |
| D4 | Keep Sortformer as a second backend | Delete it | Already written, weights already on disk. Free insurance + a real "fast mode" + a benchmark to quote. |
| D5 | faster-whisper/CT2 directly | **WhisperX** | Its alignment needs a per-language wav2vec2 phoneme model — Kazakh is not covered — and it assumes one language per file, conflicting with per-turn KZ routing. See §6. |
| D6 | whisper-large-v3-turbo + KZ fine-tune | **Voxtral** | Voxtral beats Whisper on FLEURS (~5.9% vs ~7.4% WER) but covers **13 languages, Kazakh not among them**, and needs a second runtime. Two weight files in one CT2 runtime beats two frameworks. |
| D7 | Reuse `~/ML/ML` venv | Fresh venv | A from-scratch NeMo install is the highest-variance task available to us. Snapshot it and move on. |
| D8 | Vite + React + TS + Tailwind | Next.js / Streamlit | Local-only SPA against FastAPI; no SSR boundary to fight. Streamlit would forfeit most of the 10 UI/UX points. |
| D9 | Embeddings on **CPU** | GPU embeddings | Saves ~1.2 GB VRAM for a 2 s CPU job on 16 cores. Trivially the right trade. |
| D10 | Dates resolved in Python | LLM computes dates | LLMs reliably fail at date arithmetic. Removes a whole class of scored errors. |
| D11 | Grammar-constrained JSON (Ollama `format`) | Prompt-and-parse | Schema-constrained decoding cannot emit invalid JSON or omit required evidence fields. |

---

## 6. Diarization: two backends, one interface

### Why Sortformer cannot be primary

**There is no higher-capacity Sortformer.** NVIDIA ships only 4-speaker checkpoints (`diar_sortformer_4spk-v1`, `diar_streaming_sortformer_4spk-v2`, `-v2.1`). The limit is architectural, not a runtime flag — confirmed in our own checkpoint:

```
$ tar -xOf ~/models/diar_streaming_sortformer_4spk-v2.nemo model_config.yaml | grep spks
max_num_of_spks: 4
num_spks: 4
```

That is the output-head dimension of an arrival-order-sorted transformer. Raising it requires retraining.

### Primary: pyannote community-1

```python
from pyannote.audio import Pipeline
pipe = Pipeline.from_pretrained("pyannote/speaker-diarization-community-1",
                                use_auth_token=HF_TOKEN).to(torch.device("cuda"))
ann = pipe(wav_path)                      # optional: num_speakers= / min_speakers= / max_speakers=
segments = [{"start": t.start, "end": t.end, "speaker": spk}
            for t, _, spk in ann.itertracks(yield_label=True)]
```

> **Hour-0 blocking prerequisite.** `pip install pyannote.audio`, accept the gated model terms on huggingface.co, export `HF_TOKEN`, and **pull the weights while still online**. Afterwards `HF_HUB_OFFLINE=1` makes it fully local. Discovered broken at hour 6 with Wi-Fi off, this is unrecoverable.

### Fallback / fast mode: Sortformer

`pipeline/diarize.py` exposes `diarize(wav, backend="pyannote"|"sortformer") -> segments`. Both emit the identical contract, so nothing downstream knows or cares which ran.

**Benchmark both on `~/issai/audios/*.mp3` in the 6:00–7:00 block** and put your own measured number in the pitch rather than a cited one — the most favourable published pyannote-vs-NeMo comparison is authored by pyannote.ai and should be discounted accordingly.

### Rejected: WhisperX

It bundles faster-whisper + wav2vec2 alignment + pyannote + word→speaker assignment — apparently a 1.5 h saving. But its word alignment requires a **per-language wav2vec2 phoneme model**; Russian is covered, **Kazakh is not**, and it assumes one language per file, which conflicts directly with per-turn KZ routing. Disabling alignment reduces it to a thin faster-whisper wrapper, leaving only the ~40-line max-overlap word→speaker assignment we write in `align.py`. Adopting a framework to avoid 40 lines while breaking a scored feature is a bad trade.

Also rejected: `diar_msdd_telephonic` is NeMo's only MSDD checkpoint and is 8 kHz telephony-domain — mismatched for meeting audio.

---

## 7. Architecture

```
Vite/React SPA  ──HTTP──▶  FastAPI  ──▶  SQLite (jobs, segments, items, embeddings)
      ▲                       │
      └────── SSE progress ───┤
                              ▼
                   asyncio worker · Semaphore(1) · the GPU is the queue
                              │
  ffmpeg ─▶ diarize ─▶ ASR (+KZ routing) ─▶ align ─▶ Ollama structure ─▶ verify ─▶ persist
```

One FastAPI process, one asyncio background task, one semaphore around GPU work. SSE streams `{stage, percent, elapsed}` to the UI.

### Repo layout

```
megan/
  backend/
    main.py            # FastAPI app, routes, SSE
    worker.py          # job state machine, GPU semaphore, stage load/unload
    cli.py             # headless: process one file → JSON (used by verify_offline.sh)
    schemas.py         # pydantic — single source of truth for the contract
    db.py              # SQLite, no ORM needed
    pipeline/
      audio.py         # ffmpeg normalize → 16 kHz mono wav, duration probe
      diarize.py       # diarize(wav, backend=...) -> segments
      asr.py           # faster-whisper + word timestamps + per-turn KZ routing
      align.py         # word → speaker by max temporal overlap
      speakers.py      # LLM speaker naming, inline rename propagation
      structure.py     # Ollama JSON-schema calls, map-reduce for long meetings
      verify.py        # evidence grounding + deterministic date resolution
      rag.py           # e5-small embeddings, hybrid retrieval, cited answers
      export.py        # json / csv / pdf / ics
  frontend/            # vite + react + ts + tailwind
  scripts/
    setup_models.sh
    verify_offline.sh
  docs/PLAN.md         # this document
```

### API surface

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/jobs` | multipart upload → `{job_id}`, starts processing |
| `GET` | `/api/jobs/{id}` | full result document (the contract below) |
| `GET` | `/api/jobs/{id}/events` | SSE stream of `{stage, percent, elapsed}` |
| `PATCH` | `/api/jobs/{id}/speakers` | rename `speaker_0` → "Айдар", re-propagates |
| `PATCH` | `/api/jobs/{id}/action-items/{n}` | edit an action item inline |
| `POST` | `/api/jobs/{id}/chat` | RAG question → `{answer, citations[]}` |
| `GET` | `/api/jobs/{id}/export?fmt=json\|csv\|pdf\|ics` | download |
| `GET` | `/api/jobs/{id}/audio` | range-served audio for the player |
| `GET` | `/api/health` | model status, VRAM, offline flag |

> Port note: `validator-ui`'s audio route in the existing issai project has **no path-traversal guard** (`path.join(root, rel)` with `../` unsanitized). Do not reproduce that here — resolve and assert the path stays under the job directory.

### The data contract — agree at hour 0

Dev B builds the entire UI against a fixture of this before Dev A's pipeline exists. `schemas.py` is authoritative; mirror it into `frontend/src/types.ts`.

```jsonc
{
  "job_id": "...", "status": "done",
  "duration_sec": 124.5, "elapsed_sec": 41.2,
  "meeting_date": "2026-09-11",
  "languages": ["ru", "kk"],
  "diarizer": "pyannote", "asr_model": "large-v3-turbo", "llm": "qwen3.5:9b",
  "speakers": [{ "id": "speaker_0", "name": "Айдар", "name_confidence": 0.82 }],
  "segments": [{ "id": "S12", "start": 74.2, "end": 79.8, "speaker": "speaker_0",
                 "lang": "ru", "text": "...",
                 "words": [{ "w": "...", "s": 74.2, "e": 74.5 }] }],
  "summary": ["...", "..."],                        // 3-5 sentences
  "topics":         [{ "title": "...", "theses": ["..."], "evidence": ["S12"] }],
  "decisions":      [{ "text": "...", "evidence": ["S30"], "quote": "...", "verified": true }],
  "open_questions": [{ "text": "...", "evidence": ["S44"], "quote": "...", "verified": true }],
  "risks":          [{ "text": "...", "severity": "high", "evidence": ["S51"],
                       "quote": "...", "verified": true }],
  "action_items":   [{ "assignee": "Айдар", "speaker": "speaker_0", "task": "...",
                       "due": "2026-09-19", "due_raw": "до пятницы",
                       "priority": "high", "evidence": ["S30"],
                       "quote": "...", "verified": true }],
  "stats": { "items_total": 18, "items_verified": 18, "grounding_rate": 1.0 }
}
```

---

## 8. Accuracy strategy — where 20 of the points are

The TZ scores *«корректность выделения исполнителей, дедлайнов и отсутствия галлюцинаций»*. Four deterministic mechanisms, all cheap:

**1. Numbered transcript + mandatory evidence.** The prompt feeds `[S12 | 00:03:14 | Айдар] текст…`. The JSON schema makes `evidence: string[]` and `quote: string` **required**, and Ollama's grammar-constrained decoding means the model *cannot* omit them.

**2. Post-hoc grounding check (`verify.py`).** For each item, normalize and fuzzy-match `quote` against the text of its cited segments (`rapidfuzz`, ratio ≥ 85). Failures are marked `verified: false` and rendered greyed with a warning badge rather than silently shown. Surface the rate in the UI: **"18/18 items verified against audio."** This is a concrete, demonstrable answer to the hallucination criterion — and it is honest, because it can fail visibly.

**3. Dates computed in Python, never by the LLM.** The model returns `due_raw` ("до пятницы", "к концу месяца"); a deterministic resolver converts to ISO against `meeting_date`. Handles RU/KZ relative expressions via a small pattern table; unparseable values keep `due: null` and show `due_raw` verbatim rather than inventing a date.

**4. Assignee must be a known speaker or a name found in the transcript.** Reject assignees that appear nowhere — a common hallucination mode.

**Speaker naming:** a second short LLM pass maps `speaker_0 → "Айдар"` from self-introductions and vocatives, with a confidence score. The UI allows inline rename, which re-propagates through every panel.

### The demo moment — build this early

**Every action item, decision, risk and chat answer is clickable and seeks the audio player to its cited timestamp.** The judge clicks *«Айдар готовит смету до пятницы»* and hears Айдар say it. This is simultaneously the hallucination defence and the thing people remember. It is worth more than any additional feature — if something has to be cut, cut elsewhere.

### Prompting strategy (`structure.py`)

- **Single pass** when the transcript fits in ~8k tokens (covers a 2-min jury clip and most 20-min meetings).
- **Map-reduce** beyond that: chunk on speaker-turn boundaries with ~10% overlap, extract per chunk, then a reduce pass that merges and de-duplicates. Segment IDs stay globally unique, so evidence survives the merge.
- One call produces the whole document (summary + topics + decisions + questions + risks + actions) — fewer round trips than one call per section, and the model sees the whole meeting when deciding what a "decision" is.
- Temperature 0. Thinking mode off. System prompt in Russian, since the content is RU/KZ.
- Explicitly instruct: *"If nothing in the transcript supports an item, return an empty list. Do not infer."* Empty is correct and scores better than invented.

---

## 9. RU/KZ code-switching

Two-pass, per speaker-turn:

1. Transcribe the full audio with `large-v3-turbo` (`word_timestamps=True`) — strong on RU/EN.
2. For each diarized turn, run Whisper's **language-ID head only** on that turn's audio (encoder + one decoder step — milliseconds per turn).
3. Turns scoring Kazakh above threshold are **re-decoded with the KZ model** and spliced back by timestamp.

Both models are large-v3-turbo derivatives, so this is a weight swap inside one CT2 runtime, not a second pipeline. Per-segment `lang` is recorded in the contract and shown as a small badge in the transcript UI — cheap visible proof of the multilingual bonus.

Ship behind `ENABLE_KZ_ROUTING`. If hour 5 looks tight, turn it off and the app still works.

---

## 10. RAG chat

- Chunk = one speaker turn (already have them), merged to ~40-80 words.
- Embed with `multilingual-e5-small` **on CPU** — ~2 s for a whole meeting on 16 cores, 0 VRAM.
- Store vectors as SQLite BLOBs; retrieve by brute-force numpy cosine. A meeting is a few hundred segments — an index would be premature.
- **Hybrid:** union of top-k cosine and a simple keyword/substring match, which rescues exact-term questions ("бюджет", a person's name) that dense retrieval misses.
- Answer with the same grounding contract: the LLM must cite segment IDs, and citations render as clickable timestamps.
- Answer in the language of the question.

---

## 11. Exports

| Format | Implementation | Notes |
|---|---|---|
| JSON | the contract, verbatim | trivial |
| CSV | action items table | columns: `assignee, task, due, due_raw, priority, speaker, timestamp, quote, verified` |
| PDF | **WeasyPrint** (HTML+CSS) | Cyrillic-safe with an embedded DejaVu/Noto font. **Test Cyrillic rendering at hour 4, not hour 7.** |
| ICS | `ics` package | one VEVENT per action item with a resolved `due` |

**Stretch (only if ahead of schedule):** Trello/Notion/Jira export as a **generated import file** (Trello JSON / Notion CSV), not a live API call. A live call would violate the locality requirement — this is a trap in the TZ's own bonus list. Say this out loud in the pitch; it shows you read the constraint properly.

---

## 12. 100% offline — 20 points for ~20 minutes of work

- `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` at runtime; every model resolved from a local path.
- **`scripts/verify_offline.sh`** runs the complete pipeline inside a network namespace with no interfaces:
  ```bash
  sudo unshare -n python -m backend.cli process sample.mp3
  ```
  It produces a full protocol with **no network available at all**. This is unfalsifiable proof — run it live or screenshot it into the deck.
- UI badge: **🔒 OFFLINE — 0 external requests**.
- **Turn Wi-Fi off before the demo starts.**
- Final review: grep `backend/` for any outbound host that is not `localhost`. Confirm no `openai`/`anthropic` SDK import survives.
- Do not copy `issai/audio-test/diarize.py` or `transcribe.py` into the repo at all — even unused, a reviewer finding a `mangisoz.nu.edu.kz` call is a 20-point risk.

---

## 13. Frontend

**Vite + React + TS + Tailwind.** Single page, four regions.

1. **Upload** — dropzone (MP3/WAV/M4A), then a live stage tracker driven by SSE: `decode → diarize → transcribe → analyze → verify`, each with elapsed time. The visible timer is a feature: it's the scored speed number, on screen.
2. **Protocol** — Executive Summary, Decisions, Topics & theses, Open questions, Risks. Every item carries a ▶ that seeks the audio.
3. **Transcript** — speaker-coloured, language badges, synced highlight with the audio player, inline speaker rename.
4. **Action items** — editable table (assignee / task / due / priority), verification badges, export buttons.
5. **Chat** — question box, answers with clickable citations.

Header shows: offline badge, elapsed processing time, model names, and `items_verified / items_total`. Those four facts are exactly what the rubric rewards, so keep them permanently visible.

Keep it dark, dense and fast. No animation budget.

---

## 14. Setup (`scripts/setup_models.sh`)

Runs at hour 0, in the background, while both devs scaffold.

```bash
# 1. Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3.5:9b && ollama pull qwen3.5:4b   # verify tags exist; else qwen3:8b

# 2. pyannote — GATED. Accept terms on huggingface.co first, then:
export HF_TOKEN=...
python -c "from pyannote.audio import Pipeline; \
  Pipeline.from_pretrained('pyannote/speaker-diarization-community-1', use_auth_token='$HF_TOKEN')"

# 3. Whisper → CTranslate2
ct2-transformers-converter --model openai/whisper-large-v3-turbo \
  --output_dir models/whisper-turbo-ct2 --quantization float16
ct2-transformers-converter --model shyngys879/kazakh-whisper-large-v3-turbo \
  --output_dir models/whisper-kk-ct2 --quantization float16

# 4. Embeddings
python -c "from sentence_transformers import SentenceTransformer; \
  SentenceTransformer('intfloat/multilingual-e5-small')"
```

Then **re-run one job with `HF_HUB_OFFLINE=1`** to prove nothing else is fetched at runtime.

---

## 15. Schedule — 8 hours, 2 devs

| Time | Dev A (pipeline/AI) | Dev B (backend + frontend) |
|---|---|---|
| 0:00–0:30 | **Both:** scaffold repo, write `schemas.py` + `types.ts`, commit a **fixture JSON**. A starts `setup_models.sh` and **accepts pyannote's gated terms + pulls weights while online — do this first, it is the only irreversible deadline** | |
| 0:30–2:00 | ffmpeg normalize → pyannote diarize (Sortformer behind the same interface) → faster-whisper word timestamps → `align.py`. Output = real contract JSON | FastAPI + SQLite + upload + job state + SSE; Vite shell, dropzone, stage tracker against the fixture |
| 2:00–3:30 | `structure.py` (Ollama JSON-schema) + `verify.py` grounding + date resolver + speaker naming | Protocol view: summary/decisions/questions panels, transcript with speaker colours, **audio seek-on-click** |
| 3:30–5:00 | KZ per-turn LID routing | Action items table (editable) + exports: JSON, CSV, PDF, ICS |
| 5:00–6:00 | `rag.py`: CPU embeddings, hybrid retrieval, cited answers | Chat panel, speaker rename, risks panel, polish |
| 6:00–7:00 | **Both: integration + accuracy tuning on `~/issai/audios/*.mp3`.** Measure 2-min latency. Benchmark pyannote vs Sortformer. **Feature freeze at 7:00** | |
| 7:00–8:00 | `verify_offline.sh`, README, slides, **demo rehearsal on a file nobody has heard**, buffer | |

**Hard checkpoint at 3:30** — audio → protocol must work end-to-end, however ugly. If it does not, drop KZ routing and RAG and spend 3:30–5:00 fixing it. A working must-have beats two broken bonuses: the must-have block is 70 points, the bonus block is 15.

### Fallback ladder — decide now, not at hour 6

| If this breaks | Do this |
|---|---|
| `faster-whisper`/CT2 conflicts with the venv's cuDNN | `openai-whisper` is already installed — accept ~3x slower |
| pyannote gated download / token / torch 2.11 compat fails | Flip `backend="sortformer"` — implemented, weights on disk. 4-speaker cap but fully working |
| Both diarizers fail | Whisper segments with no speaker labels. Diarization is a bonus, not a must-have |
| Ollama install fails | `llama-cpp-python`, or vLLM (already installed) with an AWQ 7B |
| `qwen3.5:9b` tag missing or OOMs | `qwen3:8b`, then `qwen3.5:4b` |
| KZ model unavailable or poor | `large-v3` full with `language="kk"` |
| WeasyPrint system libs missing | Render report HTML, use browser print-to-PDF |
| Diarizer over/under-splits speakers | Expose `num_speakers`/`min`/`max` as a UI override, re-run only that stage |
| Long meeting blows context | Map-reduce path in `structure.py` (built, not bolted on later) |

---

## 16. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| pyannote gated download not done early | Medium | **Fatal at demo time** | Hour-0 blocking task; Sortformer fallback already wired |
| Installing into `~/ML/ML` breaks it | Low | High | `uv pip freeze` snapshot before touching it |
| Jury audio is noisy / far-field | Medium | Medium | ffmpeg high-pass + loudnorm in `audio.py`; mention it |
| Jury audio has >4 speakers | Medium | Medium | pyannote is primary precisely for this |
| Jury audio is heavily code-switched | Medium | Medium | per-turn LID routing; degrade to RU-only cleanly |
| LLM invents assignees/deadlines | Medium | **20 points** | Grounding check + Python date resolution + assignee whitelist |
| 2-min processing over 45 s | Low | Up to 10 points | Fast mode toggle; measure early and often |
| Demo laptop thermal throttle | Low | Medium | Plug in mains, run one warm-up job before pitching |

---

## 17. Verification

1. `scripts/setup_models.sh` completes; `ollama list` shows `qwen3.5:9b` + `qwen3.5:4b`; both CT2 dirs exist; pyannote weights in the HF cache. **Re-run one job with `HF_HUB_OFFLINE=1`** to prove nothing is fetched at runtime.
2. `python -m backend.cli process ~/issai/audios/voice.bank-sektor-ekonomika.mp3` produces contract-valid JSON (pydantic validates), with `verified: true` on the large majority of items.
3. **Timed run:** cut a 2-minute clip with ffmpeg, run it, assert elapsed < 45 s. Scored criterion — measure, don't estimate.
4. **5+ speaker test:** build a synthetic 6-speaker clip by concatenating turns from different `~/issai/audios` recordings. Assert pyannote finds ~6, and that the Sortformer backend visibly collapses to 4 — this is the A/B that justifies D3 in the pitch.
5. **Code-switch test:** a clip with both RU and KZ turns produces correct per-segment `lang` and readable Kazakh text.
6. **Hallucination test:** feed a meeting with no action items; assert `action_items` is empty rather than invented.
7. **Full UI pass:** upload → SSE stages → click an action item → audio seeks correctly → ask a chat question → answer with working citation → export all four formats and open each.
8. `sudo ./scripts/verify_offline.sh` produces a complete protocol inside an empty network namespace.
9. Grep `backend/` for any non-`localhost` outbound host.
10. **Dry-run the whole demo on a file nobody on the team has heard.**

---

## 18. Pitch outline (5 points, ~3 minutes)

1. **The constraint first** — "100% offline. Wi-Fi is off right now." Turn it off on stage.
2. **Live run** on the jury's file. Narrate the stage tracker; land on the elapsed number.
3. **The protocol** — summary, decisions, action items.
4. **The grounding click** — "every item is a citation" → click → audio plays the exact moment. *This is the pitch.*
5. **One bonus, done well** — the RAG chat question, or the KZ/RU code-switch badge.
6. **Close on the numbers:** 2-min recording in N seconds · M/M items verified against audio · 0 external requests · runs on one laptop GPU.

Do not demo anything that was not rehearsed.
