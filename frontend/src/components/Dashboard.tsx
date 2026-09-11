import { useState } from "react";
import {
  ArrowDownUp,
  ArrowRight,
  AudioLines,
  ChevronRight,
  FileText,
  ListTodo,
  Mic,
  Search,
  Upload,
} from "lucide-react";
import type { Health, Job } from "../types";
import { formatDate, timestamp } from "../api";
import { MeetingListSkeleton } from "./Skeletons";

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
        <h1>{actionsOnly ? "Action items" : "Meetings"}</h1>
        {!actionsOnly && (
          <div className="start-actions">
            <a className="primary-button" href="#/new/record">
              <Mic size={17} /> Record a meeting
            </a>
            <a className="secondary-button" href="#/new/upload">
              <Upload size={16} /> Upload audio
            </a>
          </div>
        )}
      </div>
      <section className="meeting-library" aria-labelledby="library-title">
        <h2 id="library-title" className="sr-only">
          {actionsOnly ? "Your action items" : "Your meetings"}
          {!loading && (
            <span>{actionsOnly ? tasks.length : history.length}</span>
          )}
        </h2>
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
          <MeetingListSkeleton
            label={actionsOnly ? "Loading action items" : "Loading meetings"}
          />
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
          ? "No matches found."
          : actions
            ? "No action items yet."
            : "No meetings yet."}
      </h3>
      <p>
        {search
          ? "Try a different search or clear your filters."
          : actions
            ? "Create a meeting report to collect its action items here."
            : "Record or upload a meeting to create your first report."}
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
