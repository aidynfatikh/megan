# Natural Kazakh–Russian speech check

Tested 2026-09-11 on the development M5 with local Whisper large-v3-turbo through
whisper.cpp. This is a small diagnostic sample, not a meeting-quality certification.

Source: Timur Seidalin's [Kazakh Code-Switching ASR Benchmark](https://huggingface.co/datasets/Tim2190/kazakh-codeswitch-asr),
revision `753d6640b4b02daf6bb73307a8572c2a710c203e`. The dataset describes its audio as
natural speech drawn from CC BY YouTube recordings, with reference transcripts and
source attribution. Its clips include fast speech, contractions, slang and Russian
insertions. The author supplies both verbatim and normalized written references.

We selected every sixth row starting with the first: clips **1, 7, 13, 19, 25, 31**.
Together they contain **40.59 seconds** and **100 reference words**. The selection was
fixed before inspecting recognition results. Audio and references are retained locally
under `.local/evaluation/kazakh-codeswitch/`, outside Git.

| Setting | Word errors / reference words | WER |
| --- | --- | --- |
| Automatic language detection | 49 / 100 | 49% |
| Explicit Kazakh (`kk`) | 38 / 100 | 38% |

WER is Levenshtein word-edit distance after lowercasing and removing punctuation and
annotation tags, using the dataset's normalized written reference. It counts insertion,
deletion and substitution errors. It is not a percentage of correct meeting tasks.
No model fine-tuning or transcript cleanup was applied.

Automatic detection selected Russian for clips 1 and 19. Explicit Kazakh reduced their
errors from 8 to 4 and from 9 to 2 respectively. The other four clips remained unchanged.
This supports offering a spoken-language override; it does not establish consistently
good Kazakh or code-switch recognition.

The upload/recording screen now separates **Spoken language** from **Report language**.
For Kazakh-heavy mixed speech, try Қазақша when automatic detection gets the language
wrong. A Russian report can still be generated from Kazakh speech. The override is saved
per meeting and reused on retries, without changing other meetings' settings.

Russian remains the team's intended pitch language. Human Russian results are documented
in [QUALITY_LOG.md](QUALITY_LOG.md). Noisy rooms, simultaneous speakers, unfamiliar names
and meeting-specific dates still need a rehearsal with real reference outcomes. This
sample closes the earlier absence of any natural mixed-audio measurement, while exposing
a material quality limitation rather than proving the multilingual bonus fully accepted.
