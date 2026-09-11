import { Search } from "lucide-react";
import { useState } from "react";
import type { Job, Source } from "../types";
import { timestamp } from "../api";

export function Transcript({
  job,
  currentTime,
  selected,
  onSource,
}: {
  job: Job;
  currentTime: number;
  selected?: string;
  onSource: (source: Source) => void;
}) {
  const [search, setSearch] = useState("");
  const [voices, setVoices] = useState<string[]>([]);
  const filtering = voices.length > 0;
  const segments = job.segments.filter(
    (s) =>
      s.text.toLocaleLowerCase().includes(search.toLocaleLowerCase()) &&
      (!filtering || (s.speaker_id != null && voices.includes(s.speaker_id))),
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
      {job.speakers.length > 0 && (
        <div
          className="speaker-legend"
          role="group"
          aria-label="Filter by speaker"
        >
          {job.speakers.map((speaker, i) => (
            <button
              key={speaker.id}
              className={`speaker-chip speaker-${i % 4}`}
              aria-pressed={voices.includes(speaker.id)}
              onClick={() =>
                setVoices((current) =>
                  current.includes(speaker.id)
                    ? current.filter((id) => id !== speaker.id)
                    : [...current, speaker.id],
                )
              }
            >
              <span />
              {speaker.name}
            </button>
          ))}
        </div>
      )}
      {job.diarization_status === "done" && (
        <p className="empty-note">
          Speaker labels are estimates; check the audio before relying on one.
          Passages with multiple voices or insufficient coverage remain unknown,
          and a speaker filter hides them.
        </p>
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
            {search || filtering
              ? "No matching transcript segments."
              : "The transcript will appear here."}
          </p>
        )}
      </div>
    </section>
  );
}
