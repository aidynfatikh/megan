# Five-minute pitch demo: feasibility and rehearsal plan

The proposed demo records the team's presentation and reveals a report of what was just said. The user estimates a five-minute pitch. This plan provisionally treats that as the entire slot, including the reveal; language and additional Q&A time are still unspecified.

**Verdict:** feasible as a short live recording followed by processing during the rest of the presentation. The current app cannot record the entire five minutes and have its final report ready at the instant the pitch ends. That requires a different processing flow, and even incremental processing needs time to incorporate the final words.

## What the current app can do

| Capability | Observed state | Consequence for the pitch |
|---|---|---|
| Audio capture | `UploadView` accepts existing MP3/WAV/M4A files; no microphone capture | Use a separate local recorder or implement an in-app recorder |
| Processing | The API finishes receiving the file, then runs Whisper, optional Sortformer, and Qwen sequentially | Processing starts after the recorded passage ends and is uploaded |
| Progress | Stage/status updates already exist | Show real processing status while explaining the product |
| Report | Summary, topics, decisions, questions, risks, tasks, transcript, sources, and exports | The reveal can demonstrate the required report structure |
| Speaker labels | Optional Sortformer, up to four voices; ambiguous alignment stays unknown | Two presenters are within the model's stated capacity; room noise and real voice accuracy still need testing |
| Source playback | Tested against original recording timestamps | Play back one sentence that supports a displayed task |
| Target hardware | Mac inference tested; Fatikh's CUDA runtime and latency remain unverified | Select the actual presentation machine using rehearsals |

Relevant implementation: [upload UI](../frontend/src/components/UploadView.tsx), [upload API](../backend/main.py), [sequential worker](../backend/worker.py), [extraction prompt and size guard](../backend/pipeline/structure.py).

## Timing evidence and its limits

The [verification record](VERIFICATION.md) contains these individual Mac runs:

- 27.34 seconds of synthetic English audio: 55.50 seconds of processing with the two core models.
- 126.80 seconds / 367 words of synthetic English audio: 68.57 seconds of processing with a supplied meeting date, before the optional speaker stage was added.
- 39.09 seconds of synthetic English audio with two voices: 73.28 seconds for the full three-model pipeline, including 1.76 seconds in Sortformer.

These are neither real-room trials nor five-minute-pitch benchmarks. In the first run, report generation accounted for 52.95 seconds, so shortening the recording alone does not guarantee an almost instant report. The runs also have different inputs; they do not establish how runtime scales with recording length.

For a proposed 90-second capture, the useful planning equation is:

`reveal time = 90 seconds + stop/export/upload time + measured processing time`

A report that includes words spoken at minute five will arrive after minute five with the current pipeline. If the organizers allow extra demo time, recording the whole pitch and showing it afterward becomes a separate option.

## Recommended sequence for a five-minute slot

This is a proposed schedule, not a measured timing guarantee.

| Time | Presentation | App activity |
|---|---|---|
| 0:00–0:15 | Announce that the opening discussion will be recorded locally | Start recording; visibly check that the microphone receives speech |
| 0:15–1:15 | Explain the problem and include a short two-person discussion of actual next steps | Record the presenters |
| 1:15–1:30 | Finish the recorded passage | Stop, save, and submit it; the same-laptop handoff must fit the rehearsal |
| 1:30–3:30 | Explain the architecture, local processing, and review workflow | Process the uploaded opening passage |
| 3:30–4:30 | Reveal the report; inspect a task and play its source | Show the automatic output, then one export |
| 4:30–5:00 | Close and handle available questions | Leave the report visible |

Describe the result as a report of the recorded opening. Statements made during processing are outside that recording. A full-pitch claim would be inaccurate.

## Make the report meaningful

A product explanation supplies topics and a summary, but may contain no task assignments or new decisions. Empty sections can be the correct result. Our extraction prompt explicitly discourages filling them with invented content.

Include genuine, clearly stated next steps if they belong in the pitch: one owner and deadline, one agreed decision, and one unresolved issue. For example, only if it is an actual commitment: “Fatikh will test the CUDA setup tomorrow.” Supply the real meeting date so relative deadlines can resolve. Names, technical terms, dates, and any corrections must be checked against the recording during rehearsal.

Keep hypothetical examples distinguishable from actual commitments. A pitch saying “imagine someone assigns a task” is a different interpretation problem from a real assignment, and has not been specifically benchmarked here.

The most convincing reveal is a correct summary, one accurate task, and playback of the words just spoken. Automatic recognition of the presenters' real names is not implemented; anonymous speaker labels are expected unless a user renames them.

## Changes and tests before relying on this demo

1. **Capture and handoff.** The smallest route uses a local recorder that exports a supported file. An integrated Start/Stop recorder would remove manual file selection. Browser media recording is supported by the [MediaStream Recording API](https://www.w3.org/TR/mediastream-recording/), but the chosen browser's actual output format must be tested against our decoder. The app currently rejects WebM/OGG uploads; simply renaming their extension is not a conversion. Test microphone permission, selected input, recording retention, and stop-to-submit time.
2. **Input size.** The app's 30-minute duration setting does not guarantee that a transcript fits the report model. During this analysis, an isolated check passed invented 200- and 400-word EN/RU/KK inputs through the current size guard. At 650 words, the repeated English fixture passed; the Russian and Kazakh fixtures were rejected before any model call. These cases reused the repository's invented extraction text in 15-word segments. They establish content-dependent guard behavior only, not a universal word limit or model accuracy. Check the actual pitch transcript; adjust budgeting or add tested chunking only if necessary. Increasing the model context also needs a memory check on the target machine.
3. **Real audio.** Rehearse with both presenters, the intended language, and the actual microphone arrangement. Compare a quiet run with background chatter and interruptions. Aim the microphone at the presenters; a distant laptop microphone needs its own trial. Review names, deadlines, negations, speaker labels, and source playback against what was said.
4. **Timing and locality.** Run at least three complete rehearsals on the chosen demo laptop, including one fresh start and one repeated job. Keep external networking disabled, as required by the case. Record capture/export/upload time separately from processing and inspect memory use. Proposed acceptance for this schedule: every rehearsal yields the report by 3:00, leaving 30 seconds of buffer before the 3:30 reveal. This is a team target, not an organizer rule or reliability guarantee.
5. **Fallback.** Keep a clearly labeled rehearsal recording/report available for equipment failure. Show the current run's actual status and do not present the backup as a result of today's live capture.

The [organizer deck](AI_Steppe_Tech_Hack_Tasks.pptx), slide 4, also specifies unfamiliar jury audio and speed evaluation on a two-minute recording. The pitch recording supplements that test; it does not replace it.

## If the entire pitch must be processed while speaking

That would require microphone capture, a recording session with incremental ASR, stable original timestamps, speaker identity across chunks, and reconciliation of corrections before final report generation. The existing one-job scheduler and completed-file API do not provide this flow. Browser recording chunks are not necessarily individually playable, according to the [recording specification](https://www.w3.org/TR/mediastream-recording/), so emitting a blob periodically is not itself a working streaming pipeline.

Repeatedly calling Qwen for every fragment would also compete with the audio stages and add generation overhead. Incremental transcript collection with a final report pass is a possible design, but still leaves finalization latency. A new transcript-cleanup model does not address these capture and scheduling gaps.

No recording or streaming feature was implemented during this analysis. The proposed opening-capture sequence should become the main demo only after the real rehearsals meet the timing and accuracy criteria above.

## Subsequent real-recording test

The [YouTube meeting evaluation](YOUTUBE_TEST.md) now provides real English remote-call evidence: a two-minute excerpt completed in 67.63 seconds after a diarization rounding fix, its version with artificial pink noise in 82.89 seconds, and a five-minute excerpt in 143.56 seconds. These are processing times after upload, not recording-plus-processing times.

The tests also exposed unresolved report errors: completed work became new tasks, some assignments and conditions lacked support, and added noise damaged a name and a follow-up detail. This supports trying the proposed timing structure but does not clear the live reveal for accuracy. Actual presenters, microphone, venue, language, and Fatikh's laptop remain untested.
