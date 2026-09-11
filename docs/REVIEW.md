# AI pipeline review — 2026-09-11

A code and behaviour review of the inference path, with measurements taken on this machine. It
is not an accuracy benchmark: no model inference was run here. Speed and report-quality figures
quoted from earlier work are the Apple M5 runs recorded in [VERIFICATION.md](VERIFICATION.md)
and [YOUTUBE_TEST.md](YOUTUBE_TEST.md).

## Method

Measured directly, using the real code paths and real Sortformer output from five Russian and
Kazakh recordings (`~/issai/audio-test/audios_diarization/jsons/`, 98–673 turns each, 12–50
minutes):

- `align_speakers` and `retrieve` wall time at full meeting scale.
- Attribution outcome under Whisper-like segmentation, and the reason each segment failed.
- Prompt capacity in minutes of speech, per language.
- Upload-size behaviour against the duration policy.
- `resolve_due` coverage over realistic Russian, Kazakh and English deadline wording.
- Quote-grounding behaviour for within-segment, cross-segment, gapped and absent quotes.

Not measured here: transcription accuracy, diarization error rate, report quality, GPU latency,
VRAM. Whisper segmentation is simulated with fixed windows, which is pessimistic — real Whisper
breaks on pauses, which often coincide with speaker changes.

## Where processing time goes

The CPU-side pipeline is not a cost. At 50-minute scale (673 real turns, 429 segments):

| Stage | Time |
|---|---:|
| `align_speakers` (429 segments x 673 turns) | 6.6 ms |
| `retrieve` (per chat question) | 6.4 ms |

Against the recorded M5 runs, **report generation is 80–83% of wall clock**: 55.2 s of 67.6 s
for two minutes of audio, 119.0 s of 143.6 s for five. ASR costs 7–15 s and diarization 4–9 s.
Any optimisation that is not the language model is noise.

## Capacity: three limits that did not agree

Three independent caps governed input, and they bit at different points.

| Cap | Setting | Effective limit |
|---|---|---|
| Duration | `max_duration_sec` | 30 min |
| Upload size | `max_upload_mb` | **9 min** for 44.1 kHz stereo WAV; 6 min at 24-bit |
| Prompt capacity | `llm_context` minus output reserve | **EN 25.6 / RU 15.6 / KK 15.3 min** |

The Cyrillic penalty is structural: Russian and Kazakh get roughly 60% of English's capacity
because they tokenize worse. A 20-minute Russian meeting was accepted, decoded, transcribed and
diarized before being refused.

The size cap has been raised so that duration is the governing policy for uncompressed input.
The prompt bound is now checked immediately after transcription, before the speaker stage.

**Correction to an earlier characterisation:** the capacity guard has always run before the
HTTP request, so the language model was never wasted on an oversized transcript. The wasted work
was decode, ASR and diarization — roughly 11–24 s, not a full run.

## Speaker attribution

Measured on the real turn sets, with Whisper-like segmentation at 7 s:

| Outcome | Share |
|---|---:|
| Attributed | 67.5% |
| Unattributed — two or more voices in the segment | 23.0% |
| Unattributed — one voice below the coverage floor | 9.5% |

These need opposite treatment. Where one voice is present the uncovered remainder is silence and
no competing claim exists, so the floor was lowered from 80% to 50% and those segments are now
labelled. Where two voices share a segment the text genuinely contains both speakers; without
word-level timestamps it cannot be split, and a dominant-speaker guess would attribute one
participant's words to another. Those stay unknown deliberately.

Unattributed share fell from 32.5% to 23.3% at 7 s segments. The residual is almost entirely the
mixed case. All of this is 2-speaker audio; 3–4 speakers will straddle more.

## Deadline resolution

`resolve_due` over 25 realistic expressions, meeting on a Wednesday: **52% → 68%**.

Weekday names and bare day/month dates are now resolved against the confirmed meeting date,
which is supplied input rather than the wall clock the full-date parser deliberately refuses to
consult. Genuinely ambiguous forms still stay raw: a weekday named on that same weekday, "next
Friday", "на следующей неделе", "к концу месяца", and spelled-out numerals such as «двадцать
третьего сентября».

This resolved a disagreement between [ANALYSIS.md](ANALYSIS.md) — a weekday "should remain raw
unless the intended interpretation is unambiguous" — and a test that treated every weekday as
ambiguous. The documented rule is now the implemented one.

## Evidence grounding

Two defects were found in the check that carries the no-hallucination requirement.

**Quotes spanning ASR segments were rejected as fabrication.** Whisper splits mid-sentence, so a
model quoting one continuously spoken phrase frequently crosses a boundary. The validator could
not distinguish that from invention, and the cost was not only a review flag: `supported()`
returned false, so **the owner was dropped and the deadline marked unsupported**. Real extracted
data was being destroyed by a formatting artifact. This is the likeliest single contributor to
the 7-of-17 and 8-of-14 review-flag counts in the YouTube evaluation.

A quote is now grounded when it continues contiguously into the following segments, bounded to
four segments and a 2-second gap. The words must run without interruption and must begin in the
cited segment, which remains far stricter than searching the meeting. Source playback extends to
cover the whole quoted phrase. A quote stitched across unrelated parts of the meeting, and an
absent quote, are both still rejected.

A spanning quote cannot establish a speaker: the first-person wording may belong to whoever
spoke the continuation.

**A single common word verified a claim.** A quote of «и» passed unflagged. Action fields were
already protected, because the owner, date or priority must appear inside the quote; claims —
decisions, risks, open questions, summary, topic theses — were not. Thin claim evidence is now
surfaced for review rather than silently marked verified. One-token deadline quotes such as
"tomorrow" remain acceptable, as the extraction policy requires them.

This does not make the check semantic. Evidence linkage still means the words were said, not
that the claim drawn from them is correct.

## Remaining gaps

- **Text transcript input is unsupported.** Upload accepts only `.mp3`, `.wav`, `.m4a`. The
  specification's task description says «принимает аудиозапись встречи (или текстовый
  транскрипт)». Adding it is cheap and would also provide a demo path that needs no GPU.
- **Chat and processing share one reservation**, so a question during a running job is refused.
  Correct for memory safety, awkward in a live demonstration.
- **No chunking.** Meetings beyond the per-language ceiling are refused rather than summarised in
  parts. Reconciling superseded decisions across chunks is the hard part, not splitting text.
- **Report interpretation errors that grounding cannot catch**, carried over from the YouTube
  evaluation: completed work presented as new tasks, tentative and final states blurred. These
  produce correct citations for wrong conclusions, which mechanical validation cannot detect.

## Input that is hard to handle

Ordered by how likely it is to appear in an unfamiliar recording.

1. **Overlapping speech.** 23% of segments are multi-voice even on polite two-speaker interview
   audio, and stay unattributed by design. Interruptions and three or four speakers make it
   worse. Not fixable without word-level timestamps.
2. **More than four speakers.** The Sortformer checkpoint has four output heads and merges the
   rest into confident, wrong labels. It cannot detect that this happened.
3. **Kazakh and Russian personal names.** These compound badly: Whisper mangles names — the
   recorded noise test turned *Shin Shin* into *Jim Shim* — and owner validation requires the
   name to appear exactly inside the quote, so a mangled name silently drops the owner. Names are
   simultaneously the highest-value and least reliable tokens in the transcript.
4. **Code-switching.** One file-level language detection is stamped onto every segment, so Kazakh
   turns inside a Russian-opening meeting are decoded as Russian. Untested on real audio in
   either target language.
5. **Noise and far-field microphones.** Already measured: corrupted names, dropped details, and
   an invented condition attached to a task. The run completes; the meaning degrades precisely in
   the scored fields.
6. **Long meetings**, past the per-language ceiling.
7. **Spelled-out numerals and dates**, which never resolve.
8. **Phone and VoIP audio** at 8 kHz, upsampled.
9. **Backchannels** («да», «угу») becoming their own segments, and two participants sharing a
   first name.

## What blocks a production-quality setup

1. **Nothing has run on the RTX 4060.** No latency, no peak VRAM, no CUDA verification; the
   `.nemo` diarization adapter is entirely unexercised on that machine. Every speed figure in
   this repository is an Apple M5 result.
2. **Neither target language has been tested on real audio.** Validation so far is synthetic
   speech and real English.
3. **Report interpretation**, above — the failure mode that survives every mechanical check.
4. **Capacity** at roughly 15 minutes for Russian and Kazakh, with no chunking.
5. **Single job at a time**, no queue, no concurrent users.

## Changed in this pass

| Area | Change |
|---|---|
| `pipeline/validate.py` | Contiguous cross-segment quotes accepted; playback extended to the quoted span; spanning quotes barred from establishing a speaker; minimum evidence for claims |
| `pipeline/dates.py` | Weekday names and bare day/month dates resolved against the meeting date |
| `pipeline/structure.py` | Capacity check extracted and reusable; prompt construction shared |
| `worker.py` | Capacity checked before the speaker stage |
| `config.py` | Upload cap aligned with the duration policy |

Regression tests accompany each change and were confirmed to fail against the previous code.
