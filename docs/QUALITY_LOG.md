# Quality improvement log

This tracks the user's requested quality pass, starting from the real meeting failures in [YOUTUBE_TEST.md](YOUTUBE_TEST.md). Frontend work is excluded from commits in this pass.

## Stage 0 — preserve the measured baseline (complete)

- Pushed `46a537a` to `main`: diarization rounding fix, regression tests, and pitch/YouTube/verification notes. No frontend files were included.
- Checked the actual diff and reran all 30 diarization/runtime tests before pushing.
- Baseline real audio: natural two-minute excerpt 67.63 seconds after the rounding fix; five-minute excerpt 143.56 seconds; short excerpt with artificial pink noise 82.89 seconds.
- Problems: completed work becomes new actions; names mentioned in a passage become unsupported owners; conditions and tentative decisions are overstated; quotations span neighboring ASR segments; noise changes names and a follow-up detail. The baseline reports and source files remain in ignored local evaluation artifacts.

## Stage 1 — grounded outcomes and evidence (implemented; measured limitations below)

Targets:

1. Separate outstanding commitments from completed work, suggestions, hypothetical examples, rejected assignments, and superseded outcomes.
2. Retain legitimate tasks and their actual conditions; do not improve precision by returning empty output for every difficult case.
3. Resolve quotations across adjacent transcript segments without inventing words, moving them to an unrelated passage, or discarding original timestamps.
4. Keep named assignments separate from first-person voice ownership; a recipient or someone addressed is not automatically an assignee.
5. Apply the same interpretation discipline to summary, decisions, questions, and conditions, not just task fields.

Tests will start with failures derived from observed behavior plus independently invented positive/negative EN/RU/KK cases. Recorded test results belong below each change; a plan is not a passing result.

## Stage 2 — actual-model comparison (in progress)

Run the revised extractor against retained transcripts and compare concrete tasks, owners, dates, conditions, completed-work exclusions, decision state, and source support. Preserve draft and final outputs and compare omissions as well as inventions. Check the existing real-model regressions for regressions.

## Stage 3 — speech/noise improvement (complete; turbo retained)

Evaluate the audio stage on the unchanged natural/noisy excerpts and additional input. Test any decoding, preprocessing, or model change before selecting it. Preserve the original recording and transcript provenance; text cleanup cannot reconstruct inaudible names or dates reliably.

## Stage 4 — held-out and multilingual checks (in progress)

Use different, preselected passages/cases after development; do not tune only to the first YouTube excerpt. Measure meaning-critical errors separately from automatic-caption disagreement. Test Russian, Kazakh, mixed speech, no-task inputs, explicit assignments, corrections, and conditions. State the distinction between text tests, synthetic speech, and actual human recordings.

## Stage 5 — final verification and handoff (in progress)

Run the appropriate full backend checks and actual audio-to-report flow with the selected configuration. Record timing, resource/locality limitations, exports, and remaining material errors. Keep frontend edits out of commits. Target-laptop or venue evidence can only be claimed if actually obtained; unresolved issues stay visible.

Completion requires checked evidence for the above stages. No percentage accuracy or claim of universal/noisy-venue reliability can be inferred from a few runs or matching quotations.

### Stage 1 development evidence

- New tests first failed for cross-segment quotations, outcome filtering, recipient/owner confusion, required status generation, and condition evidence. After implementation: **41 focused tests passed**. Full normal backend suite with the dedicated PostgreSQL test database: **135 passed, 7 opt-in model tests skipped** (before adding six further real-model fixtures).
- Drafts now classify action state before report prose, and confirmed decisions are distinct from tentative or reported facts. The constrained decoder requires these fields. This remains model classification, not a semantic proof.
- Exact adjacent quotations are split back into their original timestamped segments, with a visible review reason. Missing segments, gaps, invented words, and ambiguous matches are rejected.
- Conditions now require their own source evidence. A literal condition can reuse an already valid task quote. Missing support is flagged; a potentially meaningful condition is not silently stripped to make an action unconditional. Matching a quote still does not establish the dependency's meaning.
- Baseline push CI passed: [run 34582628956](https://github.com/aidynfatikh/megan/actions/runs/34582628956).

### Stage 2 first actual-model comparison (not accepted as final)

Artifacts: `.local/evaluation/quality-20260911/phase1/`, with unchanged input transcripts, prompt/schema snapshots, draft/final reports, and timing/model receipts.

- Two-minute clean transcript: 42.67 s for extraction. Exact neighboring evidence now aligns, but the model merged confirmation and rescheduling, omitted the tentative next-week timing, and attributed summary statements to voices without sufficient support.
- Five-minute transcript: 115.64 s for extraction. Both completed-work candidates were classified `completed` and excluded from outstanding tasks. However, the remaining report still overstated a meeting decision, cited a proposal as an action, and attached the rescheduling dependency to the confirmation task. These failures prevent a quality acceptance claim.
- Next experiment: reasoning enabled in the same local model, measured separately before selecting a configuration. No change to the ASR transcript or cloud inference.

### Stage 3/4 experiment selection

- Before inference, selected the same recording's **20:00–22:00** as an unused passage. This tests another passage, not a different speaker population or domain. Selection and criteria: `.local/evaluation/quality-20260911/heldout-manifest.json`.
- Prepared an FFT denoising candidate for clean and noisy inputs using `afftdn=nr=12:nf=-25:tn=1`, based on the [FFmpeg filter documentation](https://ffmpeg.org/ffmpeg-filters.html#afftdn). Preparation is not evidence of better recognition; measure both before adoption.
- Added actual-model fixtures for completed-only work, completed plus remaining work in Russian, a hypothetical assignment and a valid conditional assignment in Kazakh, a later completion, and an explicit condition alongside irrelevant personal background. These supplement the existing EN/RU/KK/mixed cases; they are text tests, not human audio tests.

### Demo language confirmed

The user confirmed **Russian** for the pitch. Russian human audio and Russian report extraction now take priority; English and Kazakh remain regression coverage.

Selected before inference: [Идеальная планерка](https://www.youtube.com/watch?v=Lw6yYar4oP0), channel «Бизнес в стиле рэп», uploaded 2023-10-03, **10:00–12:00**. This is a human-spoken business explainer about meeting preparation and moderation, not an actual team assigning work. Its general advice/hypothetical roles should not become personal action items. Source, exact input, automatic Russian captions, and selection manifest are retained under `.local/evaluation/quality-20260911/russian/`. Captions are not supplied to inference.

The full Whisper large-v3 candidate was downloaded independently of the isolated inference processes for a measured comparison: `ggerganov/whisper.cpp` revision `5359861c739e955e79d9a303bcbc70fb988958b1`, 3,095,033,483 bytes; verified SHA-256 `64d182b440b98d5203c4f9bd541544d84c605196c4f7b845dfa11fb23594d1e2`. The default model remains turbo until results justify changing it.

### Stage 2 rejected reasoning experiment

Enabling Qwen3.5:4b reasoning with the same short transcript exhausted **8,192 output tokens** in **463.70 seconds** without any completed report content (`done_reason=length`). This mode is rejected for the live demo. Raw local experiment output, request, and receipt remain under `reasoning-120s/`; no model reasoning is presented as a report.

A Qwen3.5:9b **non-reasoning** comparison is being prepared independently, with no default change until measured. Its additional weights are setup downloads only; model execution remains sequential and local. CUDA/RTX memory and speed cannot be inferred from Mac results.

### Stage 3 measured ASR comparisons

All rows use two-minute files. Ratios compare against **automatic captions**, not an independently transcribed reference and not a percentage accuracy.

| Input / candidate | ASR seconds | Caption word edit ratio | Thursday detail in English stress case |
|---|---:|---:|---|
| Noise, turbo auto | 7.82 | 0.2677 | Missing |
| Noise, turbo + FFT filter | 7.56 | 0.2452 | Missing |
| Noise, turbo forced English | 6.56 | 0.2677 | Missing |
| Clean, turbo + FFT filter | 8.69 | 0.2323 | Present |
| Clean, turbo forced English | 6.53 | 0.2387 | Present |
| Held-out English, turbo | 7.18 | 0.1949 | Not applicable |
| Russian, turbo auto | 8.75 | 0.1810 | Not applicable |
| Russian, turbo forced Russian | 8.29 | 0.1810 | Not applicable |
| Noise, full large-v3 | 25.81 | 0.2871 | Missing |
| Clean, full large-v3 | 30.03 | 0.1871 | Present |
| Russian, full large-v3 | 49.92 | 0.1746 | Not applicable |

The filter changed names and segmentation without restoring the lost follow-up detail. Full large-v3 agreed more with captions on clean English but less on noisy English; its Russian difference was small while latency increased substantially. **Keep turbo and unfiltered audio as the default** for now. These observations do not rule out other denoisers/models or establish venue-noise accuracy. Raw inputs, canonical transcripts, recipes, and receipts are in `quality-20260911/asr/`.

### Context budgeting correction

Concurrent `main` work introduced a bytes/3 estimate to admit longer Russian transcripts. It solves an over-restrictive guard for ordinary prose, but is not an upper bound for short words or unusual text. A failing test demonstrated a 14,000-token sequence being sent despite insufficient context.

The quality pass now counts message content with a **local Qwen tokenizer**, disables tokenizer-side truncation/padding, and reserves framing/output space. Missing or unknown-model tokenizers use a strict byte fallback. Model setup downloads and checksum-verifies the 12.8 MB tokenizer; runtime never fetches it. The official 4B and 9B tokenizer files have the same SHA-256. Against the retained actual Ollama request, the local count plus framing reserve was **1,892**, versus **1,875** prompt tokens reported by Ollama. This one calibration is not a guarantee for arbitrary chat templates.

The over-budget test now passes, and the realistic Russian prose test still fits using local tokenization. Focused suite after the change: **44 passed**.

### Stage 2 expanded regression failures and next revision

The first full 4B actual-model suite produced **8 passes and 5 failures in 739.31 seconds**. Valid conditional assignments were omitted in mixed-language and English cases; a Kazakh deadline field did not match its own correct quote; anonymous first-person owners were lost when the model emitted a transcript segment ID as a voice ID and quoted only `I`.

One newly added completed-only fixture was itself ambiguous: “We are not assigning any further work today” can reasonably be summarized as a decision. Its failure is **not counted as a demonstrated factual model error**. The fixture was narrowed to completed status updates only; the original fixture and output remain retained. Both versions excluded the completed work from action items.

The next extraction revision generates source evidence before its conclusion and explicitly distinguishes conditional assignments from tentative decisions. Actual tests are ongoing; the first rerun still omitted the mixed-language conditional commitment, so prompt changes alone have not established acceptable 4B recall.

A separate grounding regression now recovers a missing/partial first-person owner quote only from the task's own exact, known-voice commitment. It uses the source's actual voice label rather than a generated segment ID or guessed speaker number, and retains review flags. Invalid citations, third-person assignments, mixed/unknown voices, and unsupported named identities retain their restrictions. Focused grounding/outcome suite: **37 passed**.

The evidence-first 4B rerun finished with **2 passes and 2 failures** across conditional/complete-work cases (212.91 s). It retained the Kazakh conditional task and correct deadline, but still omitted the mixed and English conditional tasks. The saved first-person ownership draft was separately re-grounded: named Alex remained separate from voices, and both first-person tasks recovered their actual anonymous speaker labels. This isolates the validator improvement from model generation.

Qwen3.5:9b setup completed with digest `6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7` (Q4_K_M). The temporary online download server at port 11436 was stopped after pulling. Inference uses the existing isolated port 11435. During the 16K-context Mac test, Ollama reported 5,940,130,609 bytes allocated on the GPU; this is its reported model allocation, not total machine memory or an RTX measurement.

All **148 normal backend tests passed** with the dedicated PostgreSQL test database after the current implementation changes. Thirteen real-model tests were deselected in that command and are evaluated separately.

Production jobs now retain `extraction.draft.json` and `extraction.attempts.json` locally alongside their other artifacts, including failed generation responses. This makes filtered candidates and repair attempts inspectable instead of silently losing the evidence needed to investigate an extraction failure. These are local diagnostic artifacts, not additional public report sections.

### Integrated concurrent backend changes

`main` received separate work on weekday/date parsing, speaker alignment, upload limits, early capacity checks, and weak claim evidence. Its merge temporarily conflicted with this quality pass. The resolved implementation keeps early capacity checking backed by the local tokenizer, weak-evidence warnings, and exact fragments across up to four consecutive segments. Each fragment keeps its original timestamps and voice; quotations are not accepted merely because their words occur in a later, unrelated segment. Focused post-merge checks: **83 passed**.

### 9B difficult-case results

The first 9B subset finished with **4 passes and 1 failure in 454.25 seconds**: mixed conditional assignment, completed-only updates, Kazakh conditional assignment, and anonymous speaker assignments passed. The remaining English conditional task was retained with the right owner/date but lost its condition because its task quotation began immediately after the conditional clause.

A bounded correction now recovers a literal `if`/`если`/`егер`-style prefix immediately before a unique task quote in the final transcript segment. It retains the original draft, adds the exact condition source, and marks `condition_from_task_context` for review. It avoids unrelated actions, ambiguous quote occurrences, later transcript turns, and common explicit correction cues. This is a lexical safeguard, **not a complete semantic cancellation detector**; it does not prove arbitrary conditions were interpreted correctly. EN/RU/KK positives and correction/unrelated-action negatives were tested first failing, then passing. The saved 9B failure now retains “If the checksum matches” and its source. Grounding/outcome suite after this change: **45 passed**.

### Actual human recordings with the first 9B revision

- Russian explainer: extraction completed in **87.07 s**, with no fabricated action items or decisions. The three summary points cover employee preparation, choosing a moderator/secretary, and reviewing previous tasks. Eight of nine claims had text-matching citations after adjacent-fragment alignment; one quotation still mismatched, and all nine carried review reasons. This is useful Russian output, not fully accepted citation accuracy.
- Previously unused English passage (20:00–22:00): **128.94 s**. Its summary explicitly described a commitment to adding charts/context, but `action_items` was empty. The ASR renders the word as “shots”; automatic captions render “charts.” This passage fails task recall and also shows why matching transcript text is not an audio accuracy measure.
- After that failure, the in-progress five-minute 9B extraction was stopped and its cancellation recorded; no completed timing/result is claimed. The subsequent noisy extraction in that batch was not run.

The next revision restores overview-before-actions generation, keeps evidence before individual conclusions, and explicitly requires outstanding commitments summarized elsewhere to also appear in the task list. The action-first ordering was an experiment, and the held-out failure is evidence against retaining it. This changes the previously unused passage into a regression case; it is no longer untouched hold-out evidence for later revisions.

### Overview-first results and bounded deadline correction

The 4B overview-first subset produced **2 passes and 2 failures in 270.75 s**. Mixed-language Mira was now retained, but the model translated the literal English deadline into Russian inside its citation, so grounding correctly left the date unsupported. The English Nora task was still omitted. Kazakh conditional extraction and first-person assignments passed.

A closed relative-date vocabulary now restores an equivalent original word from one exact task quote when a generated deadline citation merely translated that same word. It does not repair arbitrary invalid quotations/references, multiple relative dates, mismatched offsets, or directly negated dates. Original drafts stay unchanged and the correction adds `translated_deadline_from_task_quote` for review. Three positive tests first failed while five rejection cases passed; all eight passed after implementation. The retained Mira draft now resolves to **2026-09-12** with its original `tomorrow` source. This is a deterministic re-grounding result, not a fresh model-generation pass.

The 9B overview-first regression at 20:00–22:00 completed extraction in **72.83 s** and retained the previously missed commitment to add context/charts to the issue. Its task citation matches the ASR's word “shots”; interpreted prose says “charts,” so audio-level wording still needs review. No real name or deadline was invented for that action.

Normal backend checks after these changes: **175 passed, 13 model tests deselected** against the dedicated PostgreSQL test database. Ruff lint and formatting passed. Concurrent frontend changes are excluded from this pass.

A separate Russian positive audio fixture was prepared before inference using macOS Milena speech synthesis. It contains two explicit assignments, a corrected date, a conditional task, completed work, a decision, and an unresolved microphone choice. Its known source and expected outcomes are retained under `russian-controlled/`. It checks the audio pipeline on controlled synthetic speech; it cannot establish real-presenter or venue accuracy.


### Portable recording check

The committed helper retains the unedited job, JSON/CSV/ICS exports, input hash, model provenance from health/job data, processing stages, and audio-range status in a **new** directory:

```sh
.venv/bin/python scripts/evaluate_recording.py path/to/rehearsal.wav \
  .local/evaluation/fatikh-rehearsal-01 --language ru --meeting-date 2026-09-11
```

Use the actual recording date; omit it when unknown. Start the local API first (default helper port 8765; override with `--api`). Run one recording or direct model test at a time. Export success is an operational check; inspect whether calendar events, task owners, dates, and conditions are actually correct. This helper does not compute a human-reference accuracy score.

### 9B selection decision

The overview-first five-minute recording needed **283.89 s for extraction alone**. Completed implementation/chart updates no longer became outstanding actions, but the model mislabeled those updates as confirmed decisions, overstated agreement on the meeting time, and attached the rescheduling timing to the confirmation task. This is not acceptable evidence for promoting 9B to the default. A larger model did not consistently fix semantic errors and was substantially slower in this run.

**Selected shipped configuration remains Whisper large-v3-turbo, optional Sortformer, and Qwen3.5:4b with non-reasoning generation.** The tokenizer, outcome/evidence checks, and latest extraction ordering are retained. 9B stays a locally installed experiment; it is not an additional concurrently running stage or a requirement for Fatikh. Its CUDA memory/latency has not been tested. The final API checks below use 4B, not 9B.

### Russian controlled audio result and review correction

The **80.00 s synthetic Russian recording** completed the three-model API flow. Whisper preserved both names, the spoken correction as `18 сентября 2026 года`, `завтра`, and the database-check condition. The 4B report retained two tasks, assigned Dana's corrected date, preserved Aidar's condition, excluded completed work and the hypothetical equipment purchase, and retained the microphone question. **It omitted Aidar's tomorrow deadline despite that word being present in its exact task quote.** This prevents a fully correct report claim.

The validator now flags `possible_omitted_deadline` when a task has no deadline but its own valid quote contains a known relative-date word. It does not guess whether the date belongs to the task, a condition, or a later correction. Three EN/RU/KK warning tests first failed; they and the unrelated-turn rejection passed after implementation. Focused grounding tests: **57 passed**. Re-grounding the saved draft gives Aidar a review warning while leaving the original API report and model draft preserved. This warning was added after the initial API process started; those first saved exports do not include it.

### Distinguishing an explainer from an actual meeting

The first full 4B API run on the human Russian explainer produced no personal tasks, but mislabeled general advice about moderation and agenda order as meeting decisions. Its summary also invented a participant discussion. This is a semantic failure even when citations match.

The final prompt revision explicitly allows a recording to be a presentation, interview, or lesson; descriptions of existing practice and general advice are reported facts unless speakers explicitly adopt them in this conversation. It also forbids inventing participants who discussed or agreed. An independent Russian lecture fixture was added, alongside the existing positive assignment/decision cases. The original human-audio output is retained under `final-api/russian-human`; the final revision is evaluated separately under `final-v4/`.

The 25:00–26:30 English passage was first processed in the preceding batch, but its report was not inspected or used to make this revision. The revision is driven by the Russian explainer only. Both English runs remain retained; the final report is assessed after this prompt is frozen. This is another passage from the same source recording, not evidence from a different population.

### Confirmed-decision source gate

The genre prompt alone still mislabeled three recommendations as decisions. The final grounding change therefore requires an exact cited source with explicit adoption/agreement wording for a `confirmed` decision. It checks common EN/RU/KK forms and surrounding text within the original cited segment, including negation hidden immediately before a shortened quote. Rejected candidates remain in `extraction.draft.json`; production jobs show a decision-review warning when this gate filters candidates.

This is deliberately conservative: implicit agreements, other wording/languages, cross-turn agreement cues, or ambiguous repeated quotations may be omitted. A lexical adoption cue also cannot prove that a past decision was made in this meeting. The report remains reviewable output, not a semantic truth guarantee. Summary and topic content are retained independently.

TDD: seven advice/completion/negated/hypothetical cases initially failed while four explicit EN/RU/KK decisions passed. Two additional cases then exposed curly-apostrophe negation and a quote hiding `not`; both were fixed. **70 grounding/outcome tests passed.** Re-grounding the retained Russian explainer removes its three spurious decisions. Re-grounding the controlled Russian meeting keeps the explicitly adopted Russian demo language and both tasks. The original generated reports remain preserved; re-grounded files are separate artifacts.

### Concurrent integration checkpoint

Pushed implementation checkpoint `fa2dee2` and merge `3ec7000` to `main`, without frontend edits. Fatikh's concurrent `b376ee6`/`a211257` changes add punctuation-tolerant quote matching, a 0.2 s diarization-fragment filter, retained retrieval context, and respect for the selected context size. His measurement claims remain in `REVIEW.md`; they are not new measurements from this pass.

The merged normal backend suite passed **197 tests** with 14 real-model cases deselected. Integration then exposed two decision-gate edge cases: punctuation-only changes hid a real agreement, while the substring `agreed` inside `disagreed` looked like adoption. Both failed first and now pass with whole-word alignment back to the original segment. The focused combined suite passed **121 tests**. The final API process is restarted after these source changes; the text-model suite's saved drafts will also be re-grounded with the final merged validator.
