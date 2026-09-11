# Real YouTube meeting evaluation — 2026-09-11

**Result:** the local pipeline completed real conversational audio and exported reports. It also exposed a fixable diarization boundary bug and unresolved extraction errors. This is evidence that the system runs on real speech, not acceptance of unattended report accuracy or a noisy live pitch.

**Subsequent quality pass:** [QUALITY_LOG.md](QUALITY_LOG.md) records Russian human and controlled synthetic audio, comparisons with a larger Whisper model and Qwen 9B, outcome/evidence fixes, and the final validation results. The English measurements below are the preserved baseline; they are not silently replaced by later runs.

## Source and method

Source: GitLab Unfiltered, [Engineering Productivity Weekly — 2020-03-24](https://www.youtube.com/watch?v=U5syPVWnnYs). The [GitLab team issue](https://gitlab.com/gitlab-org/quality/quality-engineering/team-tasks/-/issues/448) links the recording as its weekly team meeting. The excerpt was selected before inference because it includes meeting-time negotiation, follow-up commitments, and an implementation update.

- Two-minute case: original video **13:20–15:20**.
- Five-minute case: original video **13:00–18:00**.
- Noise case: the identical two-minute audio mixed with seeded pink noise at a 10 dB ratio of original-clip RMS to added-noise RMS, including pauses. No samples were clipped. This is an artificial broadband-noise condition, not crowd voices or room reverberation.
- Audio was downloaded, decoded to 16 kHz mono WAV, and submitted through the real local `/api/jobs` endpoint. No captions, expected answers, or reference transcript were supplied to the app.
- The meeting date was 2020-03-24, based on the title; the upload date was the following day. Report language was English.
- Machine: the existing Apple M5 / 16 GB setup. Whisper large-v3-turbo via whisper.cpp, Sortformer via NeMo-Speech.cpp, and Qwen3.5:4b via project Ollama ran sequentially.
- API and project Ollama retained their existing loopback-only process setup. Source acquisition used the internet separately. This was not a full disconnected-machine or browser-network rehearsal.

YouTube's **automatic** captions were used only as a comparison after source selection. The review checks report support against the app's transcript and the captions; there is no independently hand-transcribed or speaker-annotated audio reference. No human-reference word error rate, diarization error rate, or percentage accuracy is claimed.

## Measured runs

Times below run from starting the local upload to observing completion. They exclude downloading and preparing the source audio and do not include the time spent recording a live meeting. Each row is one run.

| Input / implementation | Time | Speaker stage | Labeled / total transcript segments | Report tasks |
|---|---:|---|---:|---:|
| 2 min, before boundary fix | 49.34 s | Failed; report continued | 0 / 18 | 3 |
| 5 min, before boundary fix | 143.56 s | Completed, four anonymous labels | 48 / 68 | 4 |
| Same 2 min, after boundary fix | 67.63 s | Completed, three anonymous labels | 11 / 18 | 2 |
| Same 2 min + pink noise, after fix | 82.89 s | Completed, three anonymous labels | 10 / 19 | 2 |

Speaker counts and labeled-segment counts describe model output, not verified identities or attribution accuracy. Segment counts also change with ASR output. The repaired short run gives Qwen different speaker information, so its longer generation and different task count are not a timing estimate for the one-line arithmetic fix itself.

| Run | Whisper | Sortformer | Report generation |
|---|---:|---:|---:|
| 5 min | 14.75 s | 9.22 s | 119.01 s |
| 2 min after fix | 7.38 s | 4.25 s | 55.20 s |
| 2 min + noise | 8.45 s | 5.24 s | 68.95 s |

JSON, CSV, and ICS exports returned HTTP 200 for each completed run. Original-audio range requests returned HTTP 206. Calendar files had no task events because these reports had no resolved due dates; successful export is not proof of complete calendar content. The API was ready and idle after the tests, and the project Ollama model was unloaded after the last run.

## Bug found and repaired

The short recording's final RTTM turn started at `118.171` seconds and lasted `1.909` seconds. Their floating-point sum was `120.08000000000001`. Our existing 80 ms endpoint allowance evaluated to `120.08`, so a tiny numerical discrepancy rejected every speaker turn.

The implementation now adds a **1e-9 second numerical tolerance** to that bound and still clips accepted endpoints to the actual recording duration. Starts outside the recording and materially excessive endpoints remain invalid. A final duration of `1.910` seconds remains rejected.

TDD evidence: the real boundary example first failed while the just-outside-boundary rejection passed. After the fix, all **30 diarization and runtime tests passed**, along with Ruff lint/format checks. The same audio then completed the actual speaker stage; the before/after input SHA-256 matched. No ASR or Qwen prompt, model, or generation setting was changed.

Changes: [adapter](../backend/pipeline/diarize.py), [regression tests](../tests/test_diarization.py).

## Accuracy findings that remain unresolved

1. **Completed work became new tasks.** In the five-minute report, A3 and A4 describe implementing a feature and adding validation as outstanding actions even though their own evidence describes work already completed. Two of the four proposed tasks have this problem. This is a report-interpretation error, not a failure to produce valid JSON.
2. **Assignment support is inconsistent.** The initial short report assigns A3 to a person whom the quoted passage does not clearly assign the work to. After the boundary fix, the short report retains two relevant follow-ups but leaves their owners unknown. A topic statement still attributes a follow-up to a named person without establishing that identity from its cited segment.
3. **Tentative and final states are blurred.** Some summaries describe rescheduling as already completed although the follow-up discussion still calls for confirmation. Source-text matching alone does not resolve this distinction.
4. **Quotations crossing ASR segments are mis-cited.** Several generated quotes combine words from neighboring segments but name only one segment. The app flags those mismatches. The five-minute report had 7 of 17 report items marked for review; the repaired short report had 8 of 14. These are review-flag counts, not counts of all factual errors.
5. **Added noise changes task-critical information.** The name rendered as Shin Shin in the natural clip became Jim Shim in the noisy transcript. The Thursday follow-up detail disappeared. Qwen then attached an unsupported childcare-related condition to a rescheduling task. The noisy run completed, but its meaning was less dependable.

The automatic-caption comparison produced normalized word edit ratios of approximately 0.239 for the natural clips and 0.268 for the noise clip. These are exploratory disagreements between two automatic transcripts, affected by fillers, names, segmentation, and caption errors. They must not be presented as 76% or 73% transcription accuracy.

## Consequence for the pitch

The tested five-minute input required roughly **2 minutes 24 seconds after upload**. Recording for five minutes and then following the existing processing flow would reveal this result around minute 7:24, plus handoff time. It would not fit an entire five-minute presentation slot.

Recording a short opening and processing it while explaining the product remains a plausible schedule. The two-minute repaired and noise runs took about 68 and 83 seconds respectively, but actual 90-second pitch timing has not been measured. Report length and content materially affect generation time.

Before relying on the reveal, address extraction of completed versus future work, preserve conditional decisions, improve evidence spanning multiple transcript segments, and check owner attribution. Then evaluate different held-out recordings and rehearse the actual presenters, language, microphone, and demo laptop. Repeating only this known excerpt would not establish general reliability.

No live microphone capture, crowded venue, Russian/Kazakh speech, or Fatikh RTX runtime was tested here. The new arithmetic fix does not solve those limitations.

## Reproduction and retained artifacts

Source media and raw results remain ignored under `.local/evaluation/youtube-gitlab/` and the corresponding `data/jobs/` directories. They include source provenance, automatic captions, exact WAV inputs, the noise recipe, reports, exported revisions, timing receipts, and the evaluation helpers.

```sh
.venv/bin/python .local/evaluation/youtube-gitlab/run_case.py natural-120s-fixed
.venv/bin/python .local/evaluation/youtube-gitlab/run_case.py natural-300s
.venv/bin/python .local/evaluation/youtube-gitlab/run_case.py pink-noise-120s
.venv/bin/python .local/evaluation/youtube-gitlab/evaluate_results.py
```

Run model cases one at a time. The helpers require the local API and prepared inputs; these ignored artifacts are not a portable test fixture and rerunning them will replace their local receipt files.

| Case | Job ID |
|---|---|
| Natural 2 min, original implementation | `f7fc39a2-6c6c-4335-aaa9-55326e98e51d` |
| Natural 5 min | `5c121cff-7aa0-4453-849f-d311f3756ed1` |
| Natural 2 min, repaired boundary | `a56160fe-25a8-40c5-a5a6-4ae00e2b9078` |
| Noise 2 min | `53cf9068-e150-455f-8931-e6d9e3d84971` |

An initial preparation run (`37854fbf-4c46-46ea-aed3-48b888276c44`, 49.53 s) is separately retained as `pilot-preroll-120s`. The stream-copy range download had included ten seconds of preroll. The reported comparisons above instead use exact cuts decoded from the complete source audio. That preparation run was excluded for its different source interval, not its output quality.
