# Implementation and verification record

This records actual local work, separate from the planned acceptance targets in [PLAN.md](PLAN.md). Target-machine acceptance is still required on Fatikh's RTX laptop.

## Implemented

- FastAPI upload/status/history/audio/export/edit APIs and one inference scheduler.
- Local PostgreSQL migrations, persisted stages, report revisions, optimistic edit conflicts, restart recovery, and transcript-preserving retries.
- Local MP3/WAV/M4A decoding, Whisper adapters for Mac/CUDA, schema-constrained Qwen extraction, source checks, conservative dates, and unknown-field handling.
- Built React workspace with progress, report/transcript tabs, source playback, task editing, labeled example data, system status, and JSON/CSV/ICS downloads.
- Cited meeting chat reusing Qwen and keyword retrieval. No extra embedding model.
- Explicit online setup with pinned Whisper revisions/checksums; offline launch scripts; readiness CLI; dependency locks; CI checks.

Optional Sortformer speaker separation has been added with NeMo and C++ adapters; see [DIARIZATION.md](DIARIZATION.md). Long-meeting chunking, automatic speaker naming, specialized Kazakh re-decoding, PDF, and dense retrieval remain deferred. Fresh installs still default to `DIARIZATION_BACKEND=none`.

## TDD evidence

Tests were introduced before the associated backend implementations for dates, grounding, persistence, audio, extraction, jobs, exports, API, and CLI. Real inference then exposed additional failures that were reproduced as failing regression tests before fixes:

| Failure found | Regression/fix |
|---|---|
| Ollama rejected large nested bounded-string grammar rules | Simplify decoder size constraints; retain Pydantic validation and generation limits |
| Generic evidence dictionaries admitted incorrect field names | Require task/assignee/due/priority evidence fields in the draft schema |
| Dates with explicit month names remained unresolved | Anchored full-date parsing in English, Russian, and Kazakh; never invent missing year |
| Deadlines were treated as evidence of high priority | Require explicit priority wording; preserve unknown otherwise |
| Valid task quotes were present but owner/deadline citations were omitted | Reuse matching words only from that task's valid quotation, with a visible review reason |
| A negated date could be recovered from a quote | Reject recognizable negated deadline wording |

The automated suite includes real PostgreSQL integration tests. Model adapters are controlled in those tests, so they do not establish inference quality. Separate opt-in real-model tests cover selected annotated commitments. All example/test meetings are invented.

## Local environment

| Component | Observed |
|---|---|
| Machine | Apple M5, 16 GB unified memory; macOS 26.6.2 ARM64 |
| Python / PostgreSQL | 3.11.15 / 18.3 |
| Audio model/runtime | Whisper large-v3-turbo; whisper.cpp 1.9.2 on Metal |
| Report model/runtime | Qwen3.5 4B; Ollama 0.33.2, 16K context, 3500 output-token cap, thinking disabled |
| Qwen digest | `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd` |
| Database | Dedicated project PostgreSQL cluster on loopback; separate `megan_test` database |
| Frontend | React 19; Vite 6.4.3; local bundled Inter fonts |

## Results recorded so far

- 115 normal backend tests passed after the Sortformer addition; 7 opt-in model cases skipped in the normal run.
- 9 frontend tests passed; TypeScript/build passed. Dependency-lock installation and `npm audit` passed during the base implementation.
- Ruff lint/format, Git whitespace check, shell syntax, and Compose configuration checks passed.
- Real Qwen cases: no assignments (EN), corrected deadline (RU), explicit owner (KK), mentioned non-owner (EN), and conditional assignment (mixed). Four passed together; the remaining mixed case passed after the missing-citation regression fix. These test selected owners/dates/conditions and source matching, not full semantic accuracy or audio recognition quality.
- Real 27.34-second English synthetic audio completed in **55.50 seconds** with the API and Ollama under the macOS loopback-only process profile: decode 0.04s, ASR 2.44s, report stage 52.95s. Output contained the expected two tasks, owners Alex/Mira, dates 2026-09-12/2026-09-18, unspecified priorities, and the rejected-Friday decision. Ollama's process listing was empty after generation.
- A **126.80-second, 367-word synthetic English recording** was uploaded through the browser and completed in 67.57s. The native date control was left blank in that automation run, so relative dates correctly required review. A repeat through the CLI with an explicit meeting date completed in **68.57s**, retaining the two expected owners and dates. A partial deadline citation was supplemented from the same task's full quotation and remained marked for review. Both runs used the loopback-only API/Ollama profile. These are synthetic recordings, not human multilingual benchmarks.
- Real cited chat answered “Alex” to the accessibility-review ownership question with the matching S13 quotation at 37.04s. The initial chat prompt had falsely abstained; the revised prompt explicitly explains task ownership and exact citation format. The added real-model chat regression passed.
- Browser source playback sought to **7.6 seconds** and started the matching audio passage. Task editing persisted revision 2 with an `edited` marker; JSON export contained that revision, and it survived API restart. JSON/CSV/ICS endpoints were exercised.
- Browser verification used a standalone browser after the in-app runtime failed with a missing `sandboxPolicy` metadata error. A port collision with an unrelated local app was resolved by moving the Megan preview to **127.0.0.1:8765**.
- The report was visually checked at desktop and 390px mobile widths. The mobile page stays within the viewport; wide task tables scroll inside their container.
- The isolation harness was checked separately: loopback TCP succeeded; an external TCP attempt failed with `PermissionError`. This does not isolate an already-running browser; browser network inspection and the complete disconnected RTX rehearsal remain separate checks.

Raw local artifacts are in `.local/evaluation/` and are ignored by Git. Timings are individual development runs with ordinary background applications, not a statistical performance claim. Synthetic English speech is easier than unfamiliar noisy multilingual jury audio.

## Sortformer addition (2026-09-11)

- TDD cycles started with failing alignment/adapter tests, then owner-attribution and setup-checksum regressions, then UI tests. Additional failing cases covered stale optional-stage status after silence or disabling before retry. The real Qwen self-assignment test first failed and then passed after source-based speaker-ID recovery.
- NeMo-Speech.cpp **0.1.0**, Apple Silicon Metal release, and NVIDIA's Sortformer v2 Q8 GGUF were downloaded with verified SHA-256 checksums. The pinned setup script was also run against these installed artifacts. The GGUF hash is `0679cfeb1ce356d0dea9470b31274f4bfc7eb927497d82005483770666da998a`; see the model manifest for the repository revision and runtime archive hash.
- A standalone 27.34-second, single-voice synthetic recording produced one voice; the initial invocation took **8.07 seconds** including runtime startup.
- A chronological **39.09-second, two-voice synthetic meeting** (Samantha/Daniel/Samantha/Daniel) produced four corresponding diarized turns and two stable speaker labels. Nine of twelve ASR segments received labels; three crossed voice boundaries and stayed unknown.
- The final full API run completed in **73.28 seconds**, including **1.76 seconds** in the diarization stage. It retained the explicit named owner Alex independently from the speaking voice, linked two supported first-person tasks to anonymous speakers, and left the task from a mixed-boundary segment unassigned. This is one synthetic development run, not a human diarization benchmark or a 4060 speed claim.
- API, ASR/Sortformer children, and project Ollama ran under the existing macOS loopback-only process profile. Ollama had no resident model after the run. Peak GPU/RAM was not measured; the browser was not isolated by that process profile.
- Browser playback reached the original **11.58-second** source. Renaming Speaker 1 to `Samantha (test voice)` persisted revision 2, updated its linked task and JSON/CSV/ICS exports, preserved Alex's separate assignment, and survived an API restart.
- Ordinary tests include real child termination on timeout/cancellation and PostgreSQL rename/export round trips. NeMo/CUDA calls use controlled adapters here; the `.nemo` runtime remains unverified on Fatikh's hardware.

Artifacts: `.local/evaluation/sortformer-meeting/` contains the synthetic recording, expected voice turns, initial/final reports, and exports. `.local/evaluation/model-cases/speaker-assignments*.json` contains the real Qwen regression output. These remain outside Git.

## Real YouTube meeting test (2026-09-11)

See [YOUTUBE_TEST.md](YOUTUBE_TEST.md) for source intervals, retained jobs, review findings, and reproduction details. A real English GitLab meeting excerpt completed in 67.63 seconds for two minutes of audio after a timestamp-rounding fix, and a five-minute excerpt completed in 143.56 seconds. The same short audio with artificial pink noise completed in 82.89 seconds. These runs used the existing Mac models and real PostgreSQL/API flow; JSON/CSV/ICS exports and audio range responses were checked.

The first two-minute run exposed floating-point rounding at the diarizer's final-frame bound, disabling all speaker labels. A failing regression was added, a 1e-9-second numerical tolerance fixed the boundary, and the identical audio then completed diarization. All 30 diarization/runtime tests and focused Ruff checks passed. This focused verification does not replace the earlier full-suite result above.

Report accuracy remains incomplete: the longer excerpt converted completed work into new tasks, some owners/conditions lacked support, and added noise altered a name and removed a follow-up detail. Automatic YouTube captions were a secondary comparison, not human ground truth. No crowded-room microphone test, live capture, Russian/Kazakh audio test, or RTX acceptance was performed in this pass.

## Fatikh's acceptance pass

1. Confirm OS, driver, GPU/VRAM, and system RAM; use the CUDA profile and pinned files.
2. Run preflight, then a real two-minute recording through the built app. Check complete output, owners, dates, negations, conditions, timestamps, and processing time.
3. Test actual Russian, Kazakh, English, and mixed audio, including overlapping speakers, no-task meetings, noise/silence, and later corrections. Human-review the transcript and report together.
4. Measure peak GPU/system memory, cold and repeated runs, and chat → recording transitions. A Mac result does not prove 4060 compatibility or latency.
5. Rehearse disconnected startup, new upload, sources, edits, export, and restart persistence using [OFFLINE.md](OFFLINE.md).

Do not advertise the aspirational 45-second/two-minute target as measured. Human validation and RTX acceptance remain necessary before presenting the system as demo-ready.
