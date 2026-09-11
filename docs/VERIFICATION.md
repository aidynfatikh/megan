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

## Subsequent Russian quality pass — 2026-09-11

The detailed staged record is [QUALITY_LOG.md](QUALITY_LOG.md). Final validation: **199 normal backend tests**, **14 actual-model cases**, deterministic replay of saved drafts against the final merged grounding checks, and successful CI for source commit `ea95f5a`. The final real Russian two-minute video completed the isolated three-model API pipeline in **132.11 seconds**, including **10.47 seconds** of transcription. JSON/CSV/ICS exports and original-audio range playback passed. Its general advice produced no personal tasks or confirmed decisions after the source checks.

A separate controlled Russian recording preserved both named assignments and a corrected date, but omitted another deadline; that omission now receives a review flag. Some real-audio report questions and quotations remain unreliable, and an unseen English passage exposed missed conditional work. These results verify operation and specific improvements, not universal accuracy, a physical microphone, crowd noise, or Fatikh's RTX laptop.
## First RTX 4060 run (2026-09-11)

The CUDA profile was brought up on Fatikh's laptop for the first time. This closes the
"no RTX acceptance" gap; it does not replace human review of report accuracy.

| Component | Observed |
|---|---|
| Machine | RTX 4060 Laptop, 8188 MiB VRAM, driver 575.51.03, CUDA 12.9; Linux 6.11, 15 GB RAM |
| Python / PostgreSQL | 3.12.3 / 18.3 (Docker compose profile) |
| Audio model/runtime | Whisper large-v3-turbo, faster-whisper/CTranslate2 on CUDA, `int8_float16` |
| Report model/runtime | Qwen3.5 4B via the project Ollama at 127.0.0.1:11435 |
| Ollama | **0.34.0**, installed per-user under `~/.local/ollama`. The tested Mac version is 0.33.2, so this is an untested version difference. |
| Qwen digest | `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`, identical to the Mac |
| Preflight | `ready: true` for ffmpeg, asr, report_tokenizer, frontend, postgresql, ollama |

**Real Russian audio, first measurement on this machine.** A 120.0 s excerpt of a Kazakhstani
banking interview (`voice.bank-sektor-ekonomika.mp3`, 05:00–07:00) completed in **39.8 s** with
`DIARIZATION_BACKEND=none`. This is not comparable with the 132.11 s Russian run in the quality
pass above: that one ran the three-model pipeline including Sortformer on the Mac, this one ran
two models without speaker separation. Sortformer on CUDA is still unmeasured.

| Stage | Time |
|---|---:|
| decode | 0.11 s |
| transcribe (Whisper) | 8.55 s |
| analyze (Qwen, incl. 5.41 s model load) | 30.67 s |
| check_sources | 0.01 s |

Report generation is 77% of wall clock, matching the proportion recorded on the Mac. The Mac
needed 55.2 s for the report stage on two minutes of English; this machine needed 30.7 s.

Output: a Russian title and five summary sentences, one open question, and **no invented
decisions, risks or action items** — correct for an interview excerpt containing no commitments.
Six of six claims had valid references and matching quotes. One summary claim was accepted
through the adjacent-segment path and flagged `adjacent_segment_quote:claim`. Numbers survived
recognition intact (8,6 трлн / 1,3 трлн тенге).

JSON, CSV and ICS exports returned HTTP 200; the CSV carried headers only and the ICS was an
empty calendar, both correct with no action items. An audio range request returned HTTP 206.
VRAM returned to 15 MiB after the run, so the unload discipline holds on CUDA.

**A retrieval defect was found and fixed by this run.** Asked «Что сказали о кредитовании
юридических лиц?», the chat abstained. The transcript says «кредитованию» (dative) while the
question asks «кредитовании» (prepositional): the same length, so neither form contains the
other, and stem matching by prefix containment covered only suffix addition. Russian more often
substitutes an ending. Stems are now compared directly, and the same question answers from S1 at
0.0 s in 6.1 s.

Not covered by this pass: Sortformer on CUDA (`DIARIZATION_BACKEND` remained `none`), Kazakh or
code-switched audio, peak VRAM under diarization, multi-speaker attribution on real meeting
audio, repeated and concurrent runs, the browser UI, and a disconnected rehearsal. One excerpt
from one recording is not a benchmark.

### Sortformer on CUDA — first measurement (2026-09-11)

Speaker separation was then enabled on the same machine with `DIARIZATION_BACKEND=sortformer_nemo`,
`DIARIZATION_DEVICE=cuda`, and `DIARIZATION_PYTHON` pointing at the pre-existing NeMo environment
(`nemo_toolkit 2.7.0`, `torch 2.11.0+cu129`). No download was required: the historical checkpoint
at `/home/fatikh/models/diar_streaming_sortformer_4spk-v2.nemo` hashes to
`b371afce2c4958186469df33d939936b9746c89f38b10a69cfd2c61254e83329`, **identical to the pinned
manifest entry**. Preflight reported `diarization_ready: true`.

The same 120 s Russian excerpt completed the three-model pipeline in **85.1 s**.

| Stage | Two models | Three models |
|---|---:|---:|
| decode | 0.11 s | 0.13 s |
| transcribe | 7.68 s | 8.77 s |
| diarize | — | **13.93 s** |
| analyze | 27.25 s | **61.89 s** |
| total | 35.4 s | 85.1 s |

Sortformer itself costs about 14 s including NeMo and torch import in its child process. The larger
change is report generation, which more than doubled once the transcript carried speaker labels:
the prompt grows and the model writes more. Anyone budgeting demo time should use the three-model
figure, not the two-model one.

Recorded runtime was `NeMo 2.7.0 / torch 2.11.0+cu129 / cuda`. Two voices were found and **20 of
20 transcript segments received a label**, with no unknown attribution. That is a favourable case:
a two-speaker interview with clean turn-taking, where real Whisper segments break on pauses that
coincide with speaker changes. Fixed-window simulation over the same recordings predicted about
21% unknown, so the simulation is pessimistic and this result should not be generalised to
overlapping or multi-party meetings.

Report output stayed consistent with the two-model run: five summary sentences, one open question,
no invented decisions, risks or tasks, five of six claims with valid references and matching
quotes and one flagged for review. JSON, CSV and ICS exports returned HTTP 200. VRAM returned to
15 MiB after all three models had run, so sequential loading and unloading holds on CUDA.

Still unmeasured: Kazakh or code-switched audio, more than two speakers, overlapping speech, peak
VRAM during the diarization stage, repeated and concurrent runs, the browser UI on this machine,
and a disconnected rehearsal.

### Context window and the duration limit (2026-09-11, RTX 4060)

Uploading a long recording reported `Recording exceeds the 1800-second duration limit`. That cap is
the outer guard in `MAX_DURATION_SEC`, enforced at decode so an oversized file fails in under a
second instead of transcribing first. The binding constraint underneath it is the context window.

Measured with the pinned Qwen tokenizer, transcript capacity with speaker labels present:

| `LLM_CONTEXT` | transcript budget | EN | RU | KK |
|---|---:|---:|---:|---:|
| 16384 | 12628 tok | 24 min | 22 min | 16 min |
| 32768 | 29012 tok | 58 min | 53 min | 38 min |

At 16K the duration cap sat above the real ceiling for every language, so a 25-minute Russian
meeting passed the duration check and was then refused for capacity. At 32K every language clears
30 minutes, which makes `MAX_DURATION_SEC` the single binding limit rather than one of three
disagreeing ones.

32K was then measured end to end. A **1500-second (25-minute) Russian recording** completed the
three-model pipeline in **191 s**, a 0.13x realtime factor: transcribe 34.63 s, diarize 16.97 s,
analyze 138.71 s. **Peak VRAM was 4893 MiB of 8188**, sampled every five seconds, and returned to
15 MiB afterwards. 358 of 367 segments were attributed across two voices, and the report contained
four summary sentences, two open questions, four risks and no invented tasks; seven of ten claims
had valid references and matching quotes.

Re-running the two-minute clip at 32K showed no penalty for short recordings: 77.0 s against 85.1 s
at 16K, within run-to-run variation. The CUDA profile therefore ships `LLM_CONTEXT=32768`. The Mac
profile is unchanged until it is measured on that machine, since its memory behaviour differs.

Beyond 30 minutes the answer is chunking rather than a larger window, and map-reduce with
reconciliation of superseded decisions remains deferred.

### Long meetings: consecutive parts instead of a duration limit (2026-09-11, RTX 4060)

A transcript larger than the prompt budget is now read in consecutive parts and merged, so
duration is bounded by processing time and disk rather than by the context window.
`MAX_DURATION_SEC` moves to four hours and the upload cap to 700 MB.

How it works, and why it is not simply map-reduce over text:

- `plan_chunks` splits on **segment boundaries only**, so evidence identifiers and timestamps stay
  global and every quotation still points at the segment it came from. Parts overlap by two
  segments, because a commitment stated at the end of one part is often qualified at the start of
  the next.
- Each part is extracted with the **unchanged** report prompt, so per-part behaviour is the tested
  behaviour.
- Merging is a separate, narrower pass. It may only combine, drop or re-status existing items, and
  it is told to copy every `segment_id` and quote verbatim. Later parts override earlier ones,
  using the existing `superseded`, `rejected` and `completed` vocabulary — this is the semantic
  problem [ANALYSIS.md](ANALYSIS.md) identified, where a decision made early can be reversed later.
- The merged draft is then grounded against the **whole** transcript exactly as before. The merge
  therefore cannot introduce evidence: anything invented fails the quote check instead of reaching
  the report.
- Merges of many parts fold in batches; if one part cannot be merged within the context, the job
  fails with an explanation rather than looping.

**Measured.** With `LLM_CONTEXT` lowered to 16384 to force splitting, the 25-minute Russian
recording was read in **2 parts** and completed in **230 s**. Evidence in the merged report spans
`S16` to `S365` of 367 segments, so both parts contributed, and **12 of 12 claims had valid
references and matching quotes against the full transcript**. The job carries a visible warning
naming the number of parts and advising review of anything that changed mid-meeting. At the shipped
32K setting the same recording is a single part and the behaviour is unchanged: 78 s, no warning.

**A real defect surfaced here.** The first two attempts failed with `done_reason: length` at exactly
3500 output tokens. A merge mostly reproduces its inputs, so reserving the ordinary report
allowance truncated it. Merging now receives the context left over after its prompt, and batching
requires room to re-emit at least as much as was supplied.

**Known quality limitation.** In the two-part run the merged summary collapsed to a single
sentence where the policy asks for three to five, and open questions and risks grew relative to the
single-part run. Merging preserves evidence correctly but does not yet preserve summary shape.
Long-meeting output should be reviewed before it is shown to anyone.

Still unmeasured: more than two parts against real audio, meetings past one hour end to end,
Kazakh at any length, and whether supersession is actually detected when a real meeting reverses an
earlier decision.
