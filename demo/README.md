# Recorded Docker demos

These two recordings use original, scripted synthetic speech. They are intentionally
bundled so a fresh Docker workspace has playable audio, a transcript, a saved model
report, source links, speaker labels, chat and exports.

- `russian/`: 80-second Russian demo-preparation meeting, synthesized with macOS
  Milena. Original model job `4d4851b6-7f43-4b07-a9c5-ee4b8fa4ad32`.
- `two-speakers/`: 39-second English website-launch discussion, synthesized with
  macOS Samantha and Daniel. Original model job `5668ac5a-3ec0-4923-83cb-952ac1c55748`.

Both reports were generated on the development Mac with local Whisper large-v3-turbo,
Sortformer and Qwen3.5:4b. Their model provenance is retained. Import assigns dedicated
demo IDs and an initial saved revision; it does not run inference. The UI labels this
explicitly. Upload a recording to exercise processing inside Docker.

Known imperfections are retained: the Russian report flags a missed relative deadline;
some open questions interpret hypothetical content too broadly. Three English segments
cross voice boundaries and have unknown attribution. These demonstrate the need to
review a report; they are not recordings of a real meeting or proof of venue quality.

On startup, the seed inserts only missing jobs and their first report revision. Restarting
does not overwrite edited reports. User uploads and general evaluation recordings remain
ignored by Git; these curated original demo assets are the intentional exception.
