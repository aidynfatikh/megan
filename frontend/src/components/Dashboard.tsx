import { useState } from "react";
import {
  ArrowDownUp,
  ArrowRight,
  ArrowUpRight,
  AudioLines,
  CalendarDays,
  CheckCheck,
  ChevronRight,
  FileText,
  ListTodo,
  Mic,
  Plus,
  Search,
  Upload,
} from "lucide-react";
import type { Health, Job } from "../types";
import { formatDate, timestamp } from "../api";
import { navigate } from "../navigation";

const statusLabels: Record<string, string> = {
  done: "Ready to review",
  queued: "Queued",
  running: "Processing",
  failed: "Needs attention",
  interrupted: "Interrupted",
};
export function Dashboard({
  history,
  health,
  loading,
  query,
  onQuery,
  actionsOnly = false,
}: {
  history: Job[];
  health: Health | null;
  loading: boolean;
  query: string;
  onQuery: (query: string) => void;
  actionsOnly?: boolean;
}) {
  const [filter, setFilter] = useState("all");
  const [oldest, setOldest] = useState(false);
  const ready = history.filter(
    (j) =>
      j.status === "done" && j.report?.content_status !== "no_usable_speech",
  );
  const tasks = ready.flatMap((job) =>
    (job.report?.action_items ?? []).map((action) => ({ job, action })),
  );
  const search = query.toLocaleLowerCase().trim();
  const filtered = history
    .filter(
      (job) =>
        `${job.filename} ${job.report?.title ?? ""}`
          .toLocaleLowerCase()
          .includes(search) &&
        (filter === "all" ||
          (filter === "processing"
            ? ["running", "queued"].includes(job.status)
            : filter === "attention"
              ? ["failed", "interrupted"].includes(job.status) ||
                job.report?.content_status === "no_usable_speech"
              : job.status === "done" &&
                job.report?.content_status !== "no_usable_speech")),
    )
    .sort(
      (a, b) => (oldest ? 1 : -1) * a.created_at.localeCompare(b.created_at),
    );
  const filteredTasks = tasks.filter(({ job, action }) =>
    `${action.task} ${action.assignee ?? ""} ${job.report?.title ?? job.filename}`
      .toLocaleLowerCase()
      .includes(search),
  );
  return (
    <div className="dashboard panel-enter">
      <div className="dashboard-heading">
        <div>
          <span className="eyebrow">YOUR PRIVATE MEETING WORKSPACE</span>
          <h1>
            {actionsOnly ? "A clear next step." : "A little more clarity."}
          </h1>
          <p>
            {actionsOnly
              ? "The commitments from your conversations, together in one place."
              : "Your conversations, collected. Your next steps, a little clearer."}
          </p>
        </div>
        <span className="today-label">
          <CalendarDays size={15} />
          {new Date().toLocaleDateString("en-GB", {
            weekday: "short",
            day: "numeric",
            month: "short",
          })}
        </span>
      </div>
      {!actionsOnly && (
        <>
          <div className="dashboard-start">
            <div className="start-copy">
              <span className="eyebrow">
                GIVE YOUR NEXT MEETING A LITTLE SPACE
              </span>
              <h2>
                Be present.
                <br />
                We’ll keep the important bits.
              </h2>
              <div className="start-actions">
                <a className="primary-button" href="#/new/record">
                  <Mic size={17} /> Record a meeting <ArrowUpRight size={16} />
                </a>
                <a className="secondary-button" href="#/new/upload">
                  <Upload size={16} /> Upload audio
                </a>
              </div>
              <span className="capture-note">
                Microphone recording or MP3, WAV, M4A
              </span>
            </div>
            <div className="desk-illustration" aria-hidden="true">
              <div className="desk-note">
                <span>AFTER THE CONVERSATION</span>
                <strong>
                  A plan worth
                  <br />
                  coming back to.
                </strong>
                <p>
                  <CheckCheck size={15} /> Decisions, remembered.
                </p>
                <p>
                  <ListTodo size={15} /> Next steps, made clear.
                </p>
                <p>
                  <AudioLines size={15} /> The source, always there.
                </p>
              </div>
              <div className="desk-sticker">
                a clear
                <br />
                <em>way forward</em>
                <ArrowUpRight size={25} />
              </div>
            </div>
          </div>
          <div className="workspace-stats">
            <div>
              <FileText size={18} />
              <strong>{history.length}</strong>
              <span>meetings in your space</span>
            </div>
            <div>
              <CheckCheck size={18} />
              <strong>{ready.length}</strong>
              <span>ready to revisit</span>
            </div>
            <a href="#/actions">
              <ListTodo size={18} />
              <strong>{tasks.length}</strong>
              <span>action items captured</span>
              <ArrowUpRight size={14} />
            </a>
          </div>
        </>
      )}
      <section className="meeting-library" aria-labelledby="library-title">
        <div className="library-heading">
          <h2 id="library-title">
            {actionsOnly ? "Your action items" : "Your meetings"}
            <span>{actionsOnly ? tasks.length : history.length}</span>
          </h2>
          {!actionsOnly && (
            <a href="#/new/upload" className="text-button">
              <Plus size={15} /> Add a meeting
            </a>
          )}
        </div>
        <div className="library-toolbar">
          {!actionsOnly && (
            <div
              className="filter-tabs"
              role="group"
              aria-label="Filter meetings"
            >
              {[
                ["all", "All meetings"],
                ["done", "Ready"],
                ["processing", "Processing"],
                ["attention", "Needs attention"],
              ].map(([value, label]) => (
                <button
                  aria-pressed={filter === value}
                  key={value}
                  onClick={() => setFilter(value)}
                >
                  {label}
                </button>
              ))}
            </div>
          )}
          <label className="library-search">
            <Search size={16} />
            <input
              aria-label={
                actionsOnly ? "Search action items" : "Search meetings"
              }
              placeholder={
                actionsOnly ? "Find a task or owner…" : "Search your meetings…"
              }
              value={query}
              onChange={(e) => onQuery(e.target.value)}
            />
            {query && (
              <button aria-label="Clear search" onClick={() => onQuery("")}>
                ×
              </button>
            )}
          </label>
          {!actionsOnly && (
            <button
              className="sort-button"
              onClick={() => setOldest(!oldest)}
              aria-label={oldest ? "Sort newest first" : "Sort oldest first"}
            >
              <ArrowDownUp size={15} />
              <span>{oldest ? "Oldest" : "Newest"}</span>
            </button>
          )}
        </div>
        {loading ? (
          <div className="library-loading" role="status">
            <span />
            <span />
            <span />
            <p>Gathering your meetings…</p>
          </div>
        ) : actionsOnly ? (
          filteredTasks.length ? (
            <div className="all-actions">
              {filteredTasks.map(({ job, action }) => (
                <a
                  key={`${job.id}-${action.id}`}
                  href={`#/meetings/${job.id}`}
                  className="dashboard-action"
                >
                  <ListTodo size={18} />
                  <div>
                    <strong>{action.task}</strong>
                    <span>
                      {job.report?.title ?? job.filename} <i>·</i>{" "}
                      {action.assignee ?? "Unassigned"}
                    </span>
                  </div>
                  <span className="action-due">
                    {action.due.date
                      ? formatDate(action.due.date)
                      : (action.due.raw ?? "No deadline stated")}
                  </span>
                  <ChevronRight size={17} />
                </a>
              ))}
            </div>
          ) : (
            <EmptyState search={!!query} actions onClear={() => onQuery("")} />
          )
        ) : filtered.length ? (
          <div className="meeting-rows">
            {filtered.map((job) => (
              <a
                key={job.id}
                href={`#/meetings/${job.id}`}
                className="meeting-row"
              >
                <span className={`meeting-file-icon ${job.status}`}>
                  <FileText size={21} strokeWidth={1.5} />
                </span>
                <div className="meeting-row-title">
                  <strong>{job.report?.title ?? job.filename}</strong>
                  <span>
                    {job.meeting_date
                      ? formatDate(job.meeting_date)
                      : `Added ${formatDate(job.created_at)}`}
                    <i>·</i>
                    {job.duration_sec != null
                      ? `${timestamp(job.duration_sec)} audio`
                      : job.filename}
                    {job.report && (
                      <>
                        <i>·</i>
                        {job.report.action_items.length} action items
                      </>
                    )}
                  </span>
                </div>
                <span className={`job-badge ${job.status}`}>
                  <i />
                  {job.report?.content_status === "no_usable_speech"
                    ? "No speech found"
                    : statusLabels[job.status]}
                </span>
                <ChevronRight className="row-arrow" size={17} />
              </a>
            ))}
          </div>
        ) : (
          <EmptyState
            search={!!query || filter !== "all"}
            onClear={() => {
              onQuery("");
              setFilter("all");
            }}
          />
        )}
      </section>
      {!actionsOnly && (
        <button
          className="sample-invitation"
          onClick={() => navigate("/example")}
        >
          <span className="sample-icon">
            <FileText size={22} strokeWidth={1.5} />
          </span>
          <span>
            <strong>A little curious? Take a look around.</strong>
            <small>Explore an example report. No recording needed.</small>
          </span>
          <span className="sample-cta">
            Open sample <ArrowRight size={15} />
          </span>
        </button>
      )}
      {health?.busy && (
        <p className="workspace-busy" role="status">
          <span className="status-dot" /> A local request is processing. You can
          still review your saved meetings.
        </p>
      )}
    </div>
  );
}

function EmptyState({
  search,
  actions = false,
  onClear,
}: {
  search: boolean;
  actions?: boolean;
  onClear: () => void;
}) {
  return (
    <div className="library-empty">
      <span className="empty-drawing">
        {search ? (
          <Search size={25} />
        ) : actions ? (
          <ListTodo size={28} />
        ) : (
          <AudioLines size={29} />
        )}
      </span>
      <h3>
        {search
          ? "No matches just yet."
          : actions
            ? "The next steps will land here."
            : "Room for your first conversation."}
      </h3>
      <p>
        {search
          ? "Try a different search or clear your filters."
          : actions
            ? "Create a meeting report to collect its action items here."
            : "Record a meeting or bring an audio file. We’ll take it from there."}
      </p>
      {search ? (
        <button className="text-button" onClick={onClear}>
          Clear filters <ArrowRight size={14} />
        </button>
      ) : (
        <a className="text-button" href="#/new/record">
          {actions ? "Add a meeting" : "Start your first meeting"}
          <ArrowRight size={14} />
        </a>
      )}
    </div>
  );
}
