# Megan — hackathon case analysis

Reviewed 2026-09-11. This is a requirements and design review, not a report of implemented or benchmarked functionality. The reviewed starting plan is in Git commit `8dea942`; [PLAN.md](PLAN.md) contains the revised execution plan.

## 1. Recommendation

Build a local meeting report that lets a reviewer trace each decision and task back to the recording. First complete every mandatory output and one export. Then improve extraction reliability, source playback, and measured latency. Add bonuses only after that path passes an unfamiliar audio test.

The original plan identifies the right differentiator: click a task and hear its source. Its main weakness is treating an ambitious model stack, dependency setup, and several unmeasured performance claims as settled prerequisites. The user confirmed two developers, clarified that the teammate's RTX 4060 will likely run the demo, and will develop/test from an M5 Mac. Exact memory and OS details still need a target-machine preflight.

The practical model count is **two for the mandatory flow**: Whisper for transcription and Qwen for report extraction. Optional speaker diarization adds a third. Cited chat can reuse Qwen and local keyword retrieval; dense embeddings would add a fourth only if justified. Run inference stages sequentially on the demo GPU. Supporting the Mac requires a suitable ASR runtime, not another conceptual model stage.

**Subsequent database decision:** the user selected PostgreSQL. It replaces SQLite; the application will use one database engine. Run a local PostgreSQL instance on each development/demo machine and include its startup, migrations, and persistence in acceptance testing. This adds a local service to setup while retaining the offline architecture.

## 2. What the organizers actually require

Primary case sources:

- [Technical specification, PDF](TZ_AI_Meeting_Intelligence.pdf), pages 1–2: detailed requirements and scoring.
- [Hackathon deck](AI_Steppe_Tech_Hack_Tasks.pptx), slides 1–4: eight-hour format, Track 01, offline constraint, unknown jury audio, and two-minute speed evaluation. Slides 5–6 concern a different track.

Both PDF pages were read and visually inspected; slide text was extracted from the deck. The rubric below comes from the PDF, not an inferred feature weighting.

| Requirement | Required behavior | Consequence for the build |
|---|---|---|
| Audio ingestion | MP3, WAV, M4A → local transcription | All three formats need a real decode test. Text input cannot replace audio support. |
| Executive summary | 3–5 key sentences | A transcript preview or keyword list is insufficient. Avoid padding sparse input with invented facts. |
| Decisions | What participants agreed | Separate commitments from proposals, hypotheticals, and rejected options. |
| Topics and theses | Meaningful discussion blocks with their main points | These need their own report section. |
| Open questions | Matters left unresolved | Check whether later turns answered an earlier question. |
| Action items | Responsible person, task, deadline if stated, priority | Preserve unknown values. Do not manufacture owners, dates, or urgency. |
| Export | A report in CSV, JSON **or** PDF | One complete JSON report satisfies the format requirement; four exporters are unnecessary for the first milestone. |
| Autonomy | Local ASR and local LLM; no external API calls | Include the browser, model helpers, and optional features in the offline test. |

The description also permits a text transcript as input, but audio remains an explicit must-have. Transcript input is useful as a development seam and optional secondary workflow.

| Scoring category | Points | Evidence to show |
|---|---:|---|
| Functionality | 30 | A real upload produces every required section and a downloadable report. |
| AI accuracy | 20 | Correct tasks, owners, and deadlines on reviewed audio; appropriate unknowns and empty lists. |
| Locality | 20 | A new recording completes with external networking unavailable. |
| Additional features | 15 | Working speaker separation, multilingual handling, cited chat, calendar export, or risks. |
| UI/UX and performance | 10 | A clear review flow and an honestly measured two-minute run. |
| Presentation | 5 | A rehearsed explanation that also works on unfamiliar input. |

The mandatory block is **70 points**. Accuracy plus locality is **40**, not the original plan's 50. The remaining 30 includes features, UI/performance, and presentation; features alone account for 15. The rubric does not assign points to individual bonus features, so “three bonuses = nine points” would be invented.

There is **no published 45-second cutoff**, guaranteed demo language, maximum recording length, or speaker count in the supplied material. There is also no explicit disqualification procedure. The offline wording is strict enough to design for no external requests, without inventing additional organizer rules.

## 3. The actual product problem

A meeting transcript preserves words. A useful protocol preserves the meeting's final state: what was agreed, what someone undertook to do, and what remains unresolved. Those are different extraction problems.

| Transcript situation | Expected interpretation | Common failure |
|---|---|---|
| “Maybe we should launch Friday.” | Proposal; not yet an accepted launch decision | Treating a future-tense sentence as an agreement |
| “Let's launch Friday.” / “Agreed.” | Decision supported by both turns | Citing only the proposal and overlooking the response |
| “Aidar can help, but Dana will send the estimate.” | Dana owns sending the estimate | Selecting the first name mentioned |
| “I will do it.” | Link to the speaking participant only if that identity is reliable | Inventing a real name from a nearby vocative |
| “We won't launch Friday; move it to Monday.” | The later decision supersedes the earlier one | Reporting both dates as current |
| “Dana will send it if legal approves.” | Conditional task with its condition preserved | Converting a conditional undertaking into an unconditional promise |
| “Do we have approval?” followed later by “Yes.” | Resolved question | Copying every question into the open-questions list |
| No task assignments | Empty action list | Filling a schema with plausible suggestions |

The review workflow should therefore be: upload → inspect report → inspect evidence → listen → correct if needed → export. Editing is useful, but the demo must show the raw automatic result before any manual corrections; manual repair does not demonstrate extraction accuracy.

For a short jury recording, a general-purpose assistant, long chat history, or elaborate dashboard contributes less than reliable interpretation of a few specific commitments. The strongest product claim is “reviewable meeting outcomes, processed on this device.”

## 4. Audit of the starting plan

### Keep

- Local FastAPI service, React interface, and simple persistence.
- A shared result contract and a fixture so two developers can work independently.
- Timestamped evidence and click-to-listen behavior.
- A resource scheduler for local inference, with stage timings.
- Explicit fallback behavior, deterministic date arithmetic, and an unfamiliar-input rehearsal.
- Local calendar export as a possible integration bonus.

### Correct before implementation

| Priority | Finding in the original plan | Why it matters | Required correction |
|---|---|---|---|
| Critical | Linux RTX 4060, `/home/fatikh` assets, and installed packages presented as current facts | The teammate's RTX 4060 is now confirmed, but this workspace is macOS ARM64 and those paths are absent here | Use separate Mac and demo-machine profiles. Verify the teammate's OS, memory, assets, and runtime directly. |
| Critical | Quote similarity ≥85% described as verification “against audio” | A matching quote can support the wrong owner, reverse a negation, or come from incorrect ASR | Name the check `quote_match`. Separately evaluate semantic support and human audio review. |
| Critical | Running only the CLI in `unshare -n` | Its loopback cannot reach Ollama running in the host network namespace | Put all runtime services together with functioning loopback, or test the whole app with external interfaces disabled. |
| High | 9B model assumed to consume roughly 5 GB, with a 5–5.5 GB peak | The official Ollama tag lists a 6.6 GB artifact; artifact size itself still does not establish runtime memory | Measure weights, cache, buffers, device offload, and total RAM on the actual machine. |
| High | `torch.cuda.empty_cache()` treated as universal model unloading | Audio and LLM runtimes have different ownership and allocation lifetimes | Release their actual resources; isolated stage subprocesses are a straightforward fallback. |
| High | Two diarizers and Kazakh rerouting precede a complete product | Bonus setup can consume the only window for completing mandatory outputs | Diarization must be bypassable; implement one backend after the basic path. |
| High | A semaphore described as a one-item queue | A semaphore limits concurrent execution, not queued uploads; chat can race with jobs | Define admission limits and share one scheduler across all inference requests. |
| High | Synchronous inference placed inside an asyncio task | Declaring a task async does not keep synchronous model work off the API event loop | Run inference outside the event loop; keep status and audio requests responsive. |
| High | Constrained JSON said to guarantee a complete, valid result | Timeouts and truncated responses still happen; valid structure does not mean true content | Validate completion, schema, references, and semantics; allow one bounded repair. |
| High | `2026-09-19` shown for “до пятницы” | That date is Saturday; same-day Friday wording is also ambiguous | Test date rules and keep ambiguous deadlines unresolved. |
| High | Guessed speaker names and numeric model confidence | Being addressed as Aidar is not saying “I am Aidar”; model confidence is not calibrated | Default to anonymous IDs; name only from explicit evidence or user correction. |
| Medium | Missing priority semantics | The brief requires a field but does not justify assigning every task “high” or “normal” | Use `unspecified` when unstated, with a clear display label. |
| Medium | End-to-end latency estimates presented as facts | Token output length, loading, thermals, and hardware can dominate | Measure cold and repeated runs before selecting the default model. |
| Medium | Podcast recordings treated as the whole evaluation corpus | They test ASR but may contain few assignments or decisions | Add short, annotated meeting scenarios with negative examples. |
| Medium | A synthetic six-speaker concatenation treated as proof of diarization quality | Channel changes and isolated turns differ from an actual meeting; exact speaker count is not guaranteed | Use it as a stress test, alongside a manually reviewed real conversation. |
| Medium | A package freeze called a snapshot | A package list does not preserve binaries, system libraries, or a working environment | Preserve any working environment; install incompatible runtimes separately. |

The remaining issues are scope choices: automatic naming, word-level alignment, a second ASR model, RAG, PDF, ICS, speaker edits, and long-meeting map-reduce cannot all be assumed to fit in the original schedule.

## 5. Model and runtime findings

These are documentation checks as of the review date. They are **not local benchmarks**. A published model existing is distinct from its runtime loading successfully, fitting memory, or performing well on a Kazakh/Russian meeting.

| Component | What the primary source establishes | Design implication |
|---|---|---|
| Qwen3.5 via Ollama | The [9B tag](https://ollama.com/library/qwen3.5:9b) lists 6.6 GB; the [4B tag](https://ollama.com/library/qwen3.5:4b) lists 3.4 GB | Evaluate 4B first on constrained hardware; promote 9B only on measured extraction benefit. Neither number is peak RAM/VRAM. |
| faster-whisper | Its [official README](https://github.com/SYSTRAN/faster-whisper) specifies current CUDA/cuDNN dependencies and lazy transcription iteration | An existing PyTorch CUDA install is insufficient evidence. Time iteration through all segments, not generator creation. |
| Apple Silicon ASR | [CTranslate2's prebuilt GPU support](https://opennmt.net/CTranslate2/hardware_support.html) lists NVIDIA; [whisper.cpp](https://github.com/ggml-org/whisper.cpp) documents Metal support | The previous CUDA prescription is not portable to a Mac. Use a platform-appropriate ASR adapter. |
| Community-1 | The [model card](https://huggingface.co/pyannote/speaker-diarization-community-1) uses `token=`, a result with `speaker_diarization`, and documents local-path loading | The old `use_auth_token`/direct `itertracks` snippet needs updating to the installed version. Exclusive diarization is available for timestamp reconciliation. |
| Pyannote benchmarks | The same [card](https://huggingface.co/pyannote/speaker-diarization-community-1) reports 11.7% for AISHELL-4 and 20.3% for AliMeeting channel 1 | The starting plan mixes benchmark names. Those numbers cannot establish performance on our jury audio. |
| Sortformer v2 | [NVIDIA's card](https://huggingface.co/nvidia/diar_streaming_sortformer_4spk-v2) specifies at most four speakers and measures its published RTF on an RTX 6000 Ada | The limit is real for this checkpoint; the RTF is not a laptop measurement. Do not generalize to every future checkpoint. |
| Kazakh fine-tune | The [author's card](https://huggingface.co/shyngys879/kazakh-whisper-large-v3-turbo) reports improvements on its evaluated Kazakh sets and lists Kazakh/Russian code-switching among limitations | It is a candidate for testing, not proof that routing mixed turns through it improves the meeting transcript. |
| Structured output | [Ollama's documentation](https://docs.ollama.com/capabilities/structured-outputs) demonstrates schema constraints followed by response validation | Keep both, plus application-level checks. Schema constraints do not verify the meaning of extracted claims. |

There is no need to rank every contemporary ASR or LLM family. Select one viable runtime per role, then compare a small number of candidates on the actual extraction task. Generic reasoning benchmark scores are weak evidence for correct assignees and deadlines.

## 6. Accuracy: what evidence can and cannot prove

There are three separate sources of error:

1. **Recognition:** the audio said “fifteen,” the transcript says “fifty.”
2. **Attribution:** the words are correct, but assigned to the wrong speaker.
3. **Interpretation:** the words and speaker are correct, but a proposal becomes a decision.

A transcript substring check addresses only whether the supplied quotation occurs in the transcript. It cannot establish correctness at any of these three levels. Even exact matching preserves mistakes already present in ASR.

For the MVP, extract short source spans and stable segment IDs, validate their existence, and show “Source linked” or “Needs review.” Keep separate evidence for a task, its owner, its deadline, and any explicit priority. Do not let the existence of one valid quote validate all fields of an item.

Use null for unstated owners and deadlines. Preserve the original deadline expression and record whether its date was explicit, deterministically resolved, or ambiguous. Meeting date should be supplied or visibly confirmed by the user; file modification time and upload date do not establish when a meeting occurred.

The parser should handle a deliberately small set of tested relative expressions. “Tomorrow” can be resolved given a confirmed meeting date. “Friday” on a Friday, “soon,” or a date without enough calendar context should remain raw unless the intended interpretation is unambiguous. Relative expressions in Kazakh need tests written or reviewed by a speaker.

An action's owner can be a named nonparticipant or a team. A known-speaker whitelist alone would wrongly reject those assignments. A name's presence elsewhere in the transcript is likewise insufficient to confirm that person owns this task.

Human edits must be distinguishable from generated values. Changing a task's meaning should clear its prior source-check status for the changed fields. Immutable speaker IDs keep display renaming from changing identity or breaking references.

## 7. Multilingual speech and long meetings

Language switching can happen inside one speaker's turn. Per-turn language detection therefore does not solve code-switching. Very short turns also provide weak language evidence, and re-decoding every turn can lose sentence context and repeat model loading.

Start with one multilingual transcription path and preserve the spoken languages. Inspect RU, KZ, EN, and mixed examples. Language badges are metadata, not evidence that recognition is correct. Add Kazakh-specific re-decoding only if a reviewed comparison improves important names, dates, numbers, and task text. Group candidate spans into one additional model pass and preserve offsets, context, and the original transcript.

Long meetings introduce an additional semantic problem: later corrections can invalidate earlier extracted tasks or decisions. Map-reduce needs chronology, stable evidence IDs, and reconciliation of superseded outcomes, beyond deduplicating repeated text. Define a tested input limit for the hackathon build and reject unsupported lengths explicitly. This is a product limitation to disclose, not a limit stated by the organizers.

## 8. Offline operation is an end-to-end property

The target is a local browser and API using local inference, PostgreSQL, and files. Model downloads and database installation belong to setup, never a job request. The supplied materials do not specify what pre-event downloading or coding is allowed; that logistical detail should be confirmed with organizers if relevant.

Bundle fonts and frontend assets. Disable optional telemetry, cloud inference, runtime downloads, and update checks in the chosen runtime. Pyannote documents `PYANNOTE_METRICS_ENABLED=0` in its [README](https://github.com/pyannote/pyannote-audio); Ollama documents local-only operation through `OLLAMA_NO_CLOUD=1` in its [FAQ](https://docs.ollama.com/faq).

On Linux, network namespaces isolate sockets and networking resources. Consequently, a CLI in a new namespace cannot use the host's loopback Ollama server. A valid isolation harness must start the required services in the same namespace with loopback enabled and no external route. This follows from the [Linux namespace documentation](https://man7.org/linux/man-pages/man7/network_namespaces.7.html).

For any platform, first prove the full browser workflow after external interfaces are disabled, including a fresh page load and a new audio file. Record the test conditions. Add process/network observation when claiming no attempted external requests. An offline success test demonstrates the observed run; a static badge or source-code search is not a request counter.

The brief explicitly accepts `.ics` as an integration bonus. It is a clearer offline integration than promising an unspecified “Trello JSON importer.” Live external tracker API calls conflict with the stricter offline wording.

## 9. Feasibility and priority

Two developers over eight hours have at most sixteen person-hours before setup, integration, debugging, and rehearsal. The schedule should reserve time for those activities, rather than scheduling sixteen hours of features.

Recommended order:

1. Every mandatory report section, audio formats, local inference, and JSON export.
2. Evidence correctness, unfamiliar-input evaluation, source playback, useful errors, and measured latency.
3. One working diarizer if practical; use anonymous labels and allow unknown attribution.
4. A small bonus such as explicitly stated risks or calendar export.
5. RAG or specialized Kazakh routing only if the mandatory path is already stable and measurements justify the addition.

This does not assume guaranteed points. It reduces the risk that a bonus dependency prevents demonstrating the larger mandatory block.

The milestone that matters is a complete real audio → report path by roughly hour 2–3. Benchmarking first at hour 6 leaves too little time to change a runtime. Leave the final two hours for evaluation, the actual offline build, and the live-demo rehearsal.

## 10. Open facts and boundaries

| Fact | Status | Impact |
|---|---|---|
| Two developers | Confirmed by the user | Split AI pipeline ownership from API/UI ownership. |
| PostgreSQL | Selected by the user; replaces SQLite | Run locally on each machine; budget database setup and migration checks. |
| Demo hardware | Teammate's RTX 4060 is the intended target; OS and exact memory need checking | Use the NVIDIA runtime; benchmark before setting numerical latency commitments. |
| Development hardware | User reports an M5 Mac; exact variant and unified memory unspecified | Share API/UI/contracts; use a Metal-capable ASR runtime for local full-pipeline tests. |
| Eight hours and unfamiliar audio | Confirmed in supplied case | Keep early integration and a held-out rehearsal. |
| Pre-event setup rules | Not in supplied files | Count setup inside the eight hours unless permitted otherwise. |
| Typical jury language, speaker count, and duration beyond the timed clip | Not specified | Keep assumptions visible; do not tune only to familiar podcasts. |
| Existing remote models, code, and corpus | Historical claims only | Reuse only after checking accessibility, compatibility, and provenance. |

The analysis above records the planning review. Subsequent implementation downloaded the two core models on the M5 Mac, added the application and tests, and exercised local inference. Current evidence and remaining RTX checks are tracked in [VERIFICATION.md](VERIFICATION.md); launch and handoff steps are in [README.md](../README.md).

Three teammate scripts subsequently appeared under `fatikh-files/` and were read without modification. `transcribe_local.py` uses OpenAI Whisper `medium` and transcribes speaker crops; `diarize_local.py` uses Sortformer v2 and can load a local `.nemo` checkpoint, falling back to a download if absent. The core app keeps its original-time transcript and explicit setup downloads. Integrating these scripts is a deferred speaker-separation experiment; their presence does not verify the GPU environment or checkpoint availability.
