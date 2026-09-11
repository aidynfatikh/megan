import { Search } from "lucide-react";
import { useState } from "react";
import type { Job, Source } from "../types";
import { timestamp } from "../api";

export function Transcript({
  job,
  currentTime,
  selected,
  onSource,
  onRename,
}: {
  job: Job;
  currentTime: number;
  selected?: string;
  onSource: (source: Source) => void;
  onRename: (id: string, name: string) => Promise<void>;
}) {
  const [search, setSearch] = useState("");
  const [renaming, setRenaming] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const segments = job.segments.filter((s) =>
    s.text.toLocaleLowerCase().includes(search.toLocaleLowerCase()),
  );
  return (
    <section className="transcript-panel panel">
      <div className="section-heading">
        <h2>Transcript</h2>
        <span className="count">{job.segments.length}</span>
      </div>
      <label className="search-field transcript-search">
        <Search size={15} />
        <input
          placeholder="Search the conversation"
          aria-label="Search transcript"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </label>
      <div className="speaker-legend">
        {job.speakers.map((speaker, i) => (
          <button
            key={speaker.id}
            className={`speaker-chip speaker-${i % 4}`}
            disabled={job.provenance.sample}
            title="Rename speaker"
            onClick={() => {
              setRenaming(speaker.id);
              setName(speaker.name);
            }}
          >
            <span />
            {speaker.name}
          </button>
        ))}
      </div>
      {job.diarization_status === "done" && (
        <p className="empty-note">
          Speaker labels are estimates. Rename a voice after checking the audio.
          Passages with multiple voices or insufficient coverage remain unknown.
        </p>
      )}
      {renaming && (
        <form
          className="rename-form"
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              await onRename(renaming, name);
              setRenaming(null);
              setError("");
            } catch (err) {
              setError((err as Error).message);
            }
          }}
        >
          <input
            aria-label="Speaker name"
            value={name}
            maxLength={100}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <button className="secondary-button" disabled={!name.trim()}>
            Save
          </button>
          <button
            className="text-button"
            type="button"
            onClick={() => setRenaming(null)}
          >
            Cancel
          </button>
          {error && <p role="alert">{error}</p>}
        </form>
      )}
      <div className="transcript-lines">
        {segments.map((s) => {
          const speakerIndex = job.speakers.findIndex(
            (sp) => sp.id === s.speaker_id,
          );
          const speaker = job.speakers[speakerIndex];
          const active =
            selected === s.id ||
            (currentTime > 0 && currentTime >= s.start && currentTime < s.end);
          return (
            <button
              key={s.id}
              className={`transcript-line ${active ? "active" : ""}`}
              onClick={() =>
                onSource({
                  segment_id: s.id,
                  quote: s.text,
                  start: s.start,
                  end: s.end,
                })
              }
            >
              <span className="transcript-line-meta">
                <span
                  className={`speaker-name speaker-${Math.max(0, speakerIndex) % 4}`}
                >
                  {speaker?.name ?? "Speaker unknown"}
                </span>
                <span>{timestamp(s.start)}</span>
              </span>
              <span className="transcript-text">{s.text}</span>
            </button>
          );
        })}
        {!segments.length && (
          <p className="empty-note">
            {search
              ? "No matching transcript segments."
              : "The transcript will appear here."}
          </p>
        )}
      </div>
    </section>
  );
}
