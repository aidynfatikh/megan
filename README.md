# Megan

A local meeting workspace: upload MP3, WAV, or M4A; review a transcript, summary, decisions, topics, open questions, and action items; follow timestamped sources; edit tasks; export JSON, CSV, or task deadlines as ICS.

**Two models by default:** multilingual Whisper → Qwen through Ollama. Optional Sortformer adds speaker separation: Whisper → Sortformer → Qwen, still one model at a time. PostgreSQL stores jobs and report revisions. Files stay in `data/`; models stay in `models/`. No hosted inference, cloud database, analytics, or CDN assets are required at runtime.

The demo target is **Fatikh's RTX 4060 laptop**. Development uses the M5 Mac with a different Whisper runtime. GPU compatibility and demo speed must be measured on Fatikh's machine. See [verification evidence](docs/VERIFICATION.md) and the [case analysis](docs/ANALYSIS.md).

## What to push

Push code, locks, migrations, scripts, and documentation. Fatikh pulls the code, installs dependencies, downloads models on his machine, and runs the tests below. **Do not commit weights, recordings, `.env`, or PostgreSQL data.** Each laptop has its own local database; SQLite is not used.

## Setup while online

Run commands from the repository root. Use Python **3.11**, Node **22**, PostgreSQL **18.3**, ffmpeg, and local Ollama. The tested Mac tools are Ollama **0.33.2** and whisper.cpp **1.9.2**. Other versions require a smoke test. Keep roughly 10 GB free for the basic environment and weights; CUDA libraries and Docker add more.

### 1. Pick the machine profile

On the Mac, install the native tools if missing:

```bash
brew install ffmpeg whisper-cpp ollama postgresql@18
cp .env.mac.example .env
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
```

On Fatikh's laptop, use **Linux or WSL2 with working NVIDIA GPU access**. Native Windows launch scripts have not been implemented. First check `nvidia-smi`; install Python 3.11, Node 22, ffmpeg, and [Ollama](https://ollama.com/download/linux) using their platform instructions, then:

```bash
cp .env.cuda.example .env
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-cuda.lock
.venv/bin/python -m pip install --no-deps -e .
```

The CUDA lock includes CTranslate2, faster-whisper, cuBLAS 12 and cuDNN 9; the launch script locates their shared libraries. The host NVIDIA driver is a separate prerequisite. See [faster-whisper GPU requirements](https://github.com/SYSTRAN/faster-whisper#gpu). Whisper formats differ between Mac and CUDA, so copying the Mac `.bin` file to the CUDA model directory will not work.

### 2. Start PostgreSQL

Choose **one** option. Both use loopback port `54329`, the `megan` database, and the example development credentials. Change credentials in both the database setup and `.env` if needed.

```bash
# Option A: Docker, on either machine
docker compose up -d --wait postgres

# Option B: installed native PostgreSQL (initdb, pg_ctl, psql on PATH)
bash scripts/local_postgres.sh start
```

The native script creates a project-only cluster in `.local/pgdata` and also creates `megan_test`. It preserves existing data. On PostgreSQL major-version changes, use the PostgreSQL migration tools; do not initialize over an existing cluster. Database schema migrations apply automatically at API startup.

### 3. Start the project Ollama server and download models

Keep this terminal open:

```bash
bash scripts/run_ollama.sh
```

It runs a separate local server at `127.0.0.1:11435`, uses `models/ollama`, disables cloud features, and permits one loaded model/request. It does not use another Ollama application's model directory or default port.

In a second terminal:

```bash
# Choose mac OR cuda
.venv/bin/python scripts/setup_models.py --profile mac
# .venv/bin/python scripts/setup_models.py --profile cuda
```

Whisper downloads use pinned repository revisions and verified weight checksums from [model_manifest.json](scripts/model_manifest.json). Qwen's actual digest is recorded in `models/installed.json`; the script flags a changed tag digest for re-evaluation. These downloads happen only during explicit setup, never on a job request.

### 4. Build and run

```bash
cd frontend
npm ci
npm test
npm run build
cd ..
.venv/bin/megan preflight
bash scripts/run_local.sh
```

Open **http://127.0.0.1:8000**. Keep PostgreSQL, Ollama, and the API running. `preflight` checks services and artifact presence without loading models; it is not a GPU or accuracy benchmark. Start the API after building frontend assets.

If another app uses port 8000, launch with `bash scripts/run_local.sh --port 8765` and open `http://127.0.0.1:8765`. Add `--api http://127.0.0.1:8765` to CLI processing commands. For Vite development, set `MEGAN_API_URL=http://127.0.0.1:8765` when running `npm run dev`.

For UI development, run `npm run dev` inside `frontend` alongside the API; Vite proxies `/api`. The built app is the offline demo path. The API schema is at `/openapi.json`. Hosted Swagger/ReDoc assets are disabled.

## Test a real recording

For speaker labels and renaming, follow [optional Sortformer setup](docs/DIARIZATION.md). It supports Fatikh's separate NeMo environment and a pinned C++/Metal runtime on the Mac. Fresh installs default to `DIARIZATION_BACKEND=none`.

Use the browser or CLI. Meeting date is optional; leaving it blank leaves relative deadlines unresolved. Report language can be `ru`, `kk`, or `en`; evidence quotes retain their original language.

```bash
.venv/bin/megan process /path/to/meeting.wav \
  --date 2026-09-11 --language ru --output .local/my-report.json
```

Review the actual audio, not just the report's source labels. Try a two-minute recording, then a second job without restarting services. Check names, dates, negations, conditions, and later corrections. Confirm `nvidia-smi` returns to baseline between stages and after jobs. Watch system RAM as well as VRAM.

Current limits: 100 MB, 30 minutes of decoded audio, plus a conservative context-size guard. Long or dense transcripts can exceed the 16K context even below the duration limit; the saved transcript remains available. There is no long-meeting chunking in this version. CPU-heavy inference uses subprocesses; only one recording or chat request runs at a time.

## Automated checks (TDD)

The normal tests use real PostgreSQL and controlled model adapters, with no weight downloads. Create a separate test database. **Integration tests truncate only the configured database whose name ends in `_test`.** Do not point them at the app database.

```bash
# Only needed for the Docker option; the native script creates this database.
docker compose exec postgres createdb -U megan megan_test

TEST_DATABASE_URL=postgresql://megan:megan@127.0.0.1:54329/megan_test \
  .venv/bin/pytest -q
.venv/bin/ruff check backend tests scripts
.venv/bin/ruff format --check backend tests scripts
npm --prefix frontend test
npm --prefix frontend run build
```

Opt into real Qwen regression cases with Ollama running and no other inference in progress:

```bash
MEGAN_TEST_MODELS=1 .venv/bin/pytest -q tests/test_models.py
```

These include Russian corrections, Kazakh ownership, mixed-language conditions, missing tasks, and a mentioned person who is not the owner. They test selected facts against invented transcripts; they are not ASR language-quality benchmarks. Outputs are saved in `.local/evaluation/model-cases/` for human review.

After backend response schema changes:

```bash
.venv/bin/python scripts/export_schema.py
npm --prefix frontend run generate:types
```

## Offline rehearsal and recovery

After setup, disable external network access on the demo machine. Start PostgreSQL, the project Ollama server, and the built app; open a fresh browser tab; upload an unfamiliar recording; inspect sources; export; restart the API and reopen the saved report. Test chat if you will present it. Browser fonts and scripts are bundled locally. The complete procedure and a macOS process-isolation harness are in [OFFLINE.md](docs/OFFLINE.md).

On failure, open **System status**, inspect terminal logs, and fix the missing service or artifact. Failed/interrupted jobs retain their saved transcript and offer **Retry processing**. One API process owns the database runner lease; do not launch multiple workers. PostgreSQL must be available at API startup. Source-linked task edits are saved as new report revisions, and stale edits are rejected.

“Source linked” means exact text was located in the transcript, not that the claim was semantically or acoustically verified. Unknown owner/priority/date values stay unknown. An owner or deadline citation recovered from exact words in a task quotation is visibly marked for review. Ambiguous weekday/year wording is not guessed. The example report is explicitly illustrative and has no recorded audio.

Automatic speaker naming, dense embeddings, specialized Kazakh re-decoding, PDF output, and long-meeting chunking are deferred. This release provides transcription/reporting, optional Sortformer speaker labels with manual renaming, task edits, JSON/CSV/ICS, and cited keyword-based meeting chat.
