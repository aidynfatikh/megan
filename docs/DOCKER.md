# Run the complete app in Docker

The Docker app contains the web interface, Python API, PostgreSQL, local Ollama,
Whisper and Sortformer runtimes. It starts with two recorded demo meetings, including
their audio, transcript and saved report. Nothing needs to be processed before you can
open them.

## On this Mac, with the models already downloaded

From the repository root:

```bash
docker compose -f compose.app.yaml up -d --build --wait
```

Open **http://127.0.0.1:8766/#/workspace**. Select the Russian demo-preparation meeting
or the English two-speaker website discussion. Play audio, open a source timestamp,
review/edit a task, rename a speaker in Transcript, ask a question, or export the report.

The `Recorded demo` banner identifies prerecorded synthetic speech and an earlier
Mac-generated report. Upload or record new audio to exercise all three models inside
Docker. Models run sequentially to limit memory usage.

Use the same start command after pulling code changes. Reports, audio, edits, Notion
connections and export receipts persist in Docker volumes. Startup inserts demo meetings
only when their IDs are missing; it preserves your edits.

```bash
# See service status and recent application logs
docker compose -f compose.app.yaml ps
docker compose -f compose.app.yaml logs --tail=80 app

# Stop while retaining meetings and downloaded models
docker compose -f compose.app.yaml down
```

The earlier `docker compose up -d postgres` command starts **only a database** for the
native app. `compose.app.yaml` is a separate project and volume, and does not replace
the native database at port 54329. The complete Docker app uses port 8766. Set
`MEGAN_DOCKER_PORT` if another program uses it.

## First setup on a different machine

Install Docker with Compose v2 supporting optional env files (Compose 2.24 or newer).
Start Docker Desktop where applicable. Allow at least 8 GB of Docker memory; 12 GB
provides more room. Images, native libraries and models require several GB of downloads
and substantially more disk space after extraction.

```bash
docker compose -f compose.app.yaml build
docker compose -f compose.app.yaml up -d --wait postgres ollama
docker compose -f compose.app.yaml --profile setup run --rm setup
docker compose -f compose.app.yaml up -d --wait app
```

The explicit setup step downloads and verifies Whisper weights, the tokenizer and
Sortformer, and pulls Qwen3.5:4b. They live in the ignored `models/` directory and are
reused across container rebuilds. The setup script's `--profile mac` selects the GGML
Whisper file format; the Docker runtime itself is Linux and runs on CPU.

After setup, inference needs no internet connection. Optional Notion export does.
No Notion credentials or downloaded models are included in the built image or Git.

## Performance and the presentation laptop

Docker Desktop on this Mac runs the Linux CPU versions of Whisper and Sortformer;
it does not pass the Mac's Metal GPU through to these containers. Use the native Mac
setup for faster local processing. The saved Docker demos remain immediately available.

### Faster Docker app on this Mac

Keep the app, database and speech models in Docker, and use native Ollama with the
Mac GPU for report generation and chat. Start Ollama in another terminal if it is
not already running:

```bash
bash scripts/run_ollama.sh
```

Then start the app:

```bash
docker compose -f compose.app.yaml -f compose.mac.yaml up -d --build --wait
```

The app stays at port 8766. Native Ollama must remain running on port 11435
(overridable with `MAC_OLLAMA_PORT`). Wait for active processing to finish before
switching modes. The base command above returns to running all models inside Docker.

### NVIDIA option

On Fatikh's Linux NVIDIA machine, an optional override gives Ollama access to the GPU:

```bash
docker compose -f compose.app.yaml -f compose.gpu.yaml up -d --build --wait
```

This requires a working NVIDIA driver and NVIDIA Container Toolkit. The override
accelerates Ollama only; Whisper and Sortformer remain CPU versions in this portable
image. The native CUDA/NeMo setup in [DIARIZATION.md](DIARIZATION.md) is the separate
path for all model stages on the NVIDIA GPU. This Mac cannot verify RTX performance.

The team has decided to use completed reports for the presentation. For normal use,
allow the models to finish in the background; saved reports can be explored immediately.

## Notion

The running local setup is connected to a dedicated **Megan Meetings** database.
Open a completed meeting and click **Export to Notion**. This sends its report,
conditions, review states and cited passages to Notion; audio stays local. The resulting
link appears in the app. Clicking again reuses the same exported revision. Editing a
report creates a new revision, which exports to a new page and preserves earlier pages.

For another workspace, use **Connection settings**. Enter a Notion API token. Leave
IDs blank to create a private database with a personal access token; internal connections
need a shared parent page ID. An existing destination must be a Megan-shaped **data
source ID**, rather than the database ID or a page URL. The connection is checked before
being saved. Its token is stored in a private server-side file in the app's data volume.

Alternatively, copy `.env.notion.local.example` to `.env.notion.local` and fill in the
token and data source ID before starting Docker. The file is optional and ignored by
Git. Settings saved through the UI take precedence on later restarts.

If Notion times out after a page might have been created, the app checks the destination
for that meeting/revision before trying again. An uncertain write is not blindly retried.
If it remains uncertain, check Notion before making another export. Core recording,
reporting and downloads work without a Notion connection.

## Why direct API export rather than a Notion Worker?

Notion Workers are hosted automations for recurring syncs, webhooks and agent tools.
This case needs a local app and an explicit report export. Direct API calls keep that
flow simple; the supplied credential successfully created the dedicated destination.
A Worker would be useful later for scheduled sync or Notion-side agent actions.

References: [Workers overview](https://developers.notion.com/workers/get-started/overview),
[create database](https://developers.notion.com/reference/create-database),
[create page with Markdown](https://developers.notion.com/reference/post-page),
[Notion request limits](https://developers.notion.com/reference/request-limits),
[Docker Desktop GPU support](https://docs.docker.com/desktop/features/gpu/).
