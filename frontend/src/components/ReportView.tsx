import {
  AlertCircle,
  ArrowUpRight,
  Check,
  CheckCheck,
  CircleHelp,
  Flag,
  ListTodo,
  Pencil,
  Play,
  Quote,
} from "lucide-react";
import type { Action, Claim, Job, Source } from "../types";
import { formatDate, timestamp } from "../api";

export function SourceButton({
  source,
  onSource,
}: {
  source: Source;
  onSource: (source: Source) => void;
}) {
  return (
    <button
      className="source-button"
      aria-label={`View source ${source.segment_id} at ${timestamp(source.start)}`}
      onClick={() => onSource(source)}
    >
      <Play size={10} fill="currentColor" /> {timestamp(source.start)}
    </button>
  );
}

function SourceLinks({
  sources,
  onSource,
}: {
  sources: Source[];
  onSource: (source: Source) => void;
}) {
  return (
    <span className="source-links">
      {sources.map((s, i) => (
        <SourceButton
          key={`${s.segment_id}-${i}`}
          source={s}
          onSource={onSource}
        />
      ))}
    </span>
  );
}

function ClaimList({
  items,
  empty,
  onSource,
}: {
  items: Claim[];
  empty: string;
  onSource: (s: Source) => void;
}) {
  if (!items.length) return <p className="empty-note">{empty}</p>;
  return (
    <ul className="claim-list">
      {items.map((item) => (
        <li key={item.id}>
          <div>
            <span>{item.text}</span>{" "}
            <SourceLinks sources={item.evidence} onSource={onSource} />
          </div>
          {item.review.state === "needs_review" && (
            <span className="review-note">
              <AlertCircle size={12} /> Needs review
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

export function ReportView({
  job,
  onSource,
  onEdit,
}: {
  job: Job;
  onSource: (source: Source) => void;
  onEdit: (item: Action) => void;
}) {
  const report = job.report;
  if (!report) return null;
  return (
    <div className="report-stack">
      {report.content_status === "no_usable_speech" && (
        <div className="notice">
          <AlertCircle size={18} /> No usable speech was detected. Try a clearer
          recording.
        </div>
      )}
      <section className="summary-card">
        <div className="section-heading">
          <span className="section-icon">
            <Quote size={18} />
          </span>
          <h2>Executive summary</h2>
          <span className="eyebrow section-meta">THE BIG PICTURE</span>
        </div>
        <div className="summary-content">
          {report.summary.length ? (
            report.summary.map((item) => (
              <p key={item.id}>
                {item.text}{" "}
                <SourceLinks sources={item.evidence} onSource={onSource} />
                {item.review.state === "needs_review" && (
                  <span className="review-note">Needs review</span>
                )}
              </p>
            ))
          ) : (
            <p className="empty-note">No supported summary is available.</p>
          )}
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <span className="section-icon green">
            <CheckCheck size={19} />
          </span>
          <h2>Decisions</h2>
          <span className="count">{report.decisions.length}</span>
        </div>
        <ClaimList
          items={report.decisions}
          empty="No explicit decisions were found."
          onSource={onSource}
        />
      </section>

      <section className="panel action-panel">
        <div className="section-heading">
          <span className="section-icon">
            <ListTodo size={19} />
          </span>
          <h2>Action items</h2>
          <span className="count">{report.action_items.length}</span>
          <span className="section-meta muted">Clear next steps</span>
        </div>
        {report.action_items.length ? (
          <div className="table-scroll">
            <table className="action-table">
              <thead>
                <tr>
                  <th>Task / owner</th>
                  <th>Due date</th>
                  <th>Priority</th>
                  <th>Source</th>
                  <th>
                    <span className="sr-only">Edit</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {report.action_items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <div className="task-title">{item.task}</div>
                      <div className="task-owner">
                        <span className="avatar tiny">
                          {(
                            item.assignee ??
                            job.speakers.find((s) => s.id === item.speaker_id)
                              ?.name ??
                            "?"
                          ).slice(0, 1)}
                        </span>
                        {item.assignee ??
                          job.speakers.find((s) => s.id === item.speaker_id)
                            ?.name ??
                          "Unassigned"}
                        {item.review.state === "edited" ? (
                          <span className="mini-label">Edited</span>
                        ) : item.review.state === "needs_review" ? (
                          <span className="mini-label warning">
                            Needs review
                          </span>
                        ) : null}
                      </div>
                      {item.conditions.length > 0 && (
                        <div className="conditions">
                          If: {item.conditions.join("; ")}
                        </div>
                      )}
                    </td>
                    <td>
                      <span className="date-text">
                        {item.due.date
                          ? formatDate(item.due.date)
                          : (item.due.raw ?? "No deadline stated")}
                      </span>
                      {!item.due.date && item.due.raw && (
                        <small className="muted">Unresolved date</small>
                      )}
                    </td>
                    <td>
                      <span className={`priority ${item.priority}`}>
                        {item.priority === "unspecified"
                          ? "Not specified"
                          : item.priority}
                      </span>
                    </td>
                    <td>
                      <SourceLinks
                        sources={item.evidence.task ?? []}
                        onSource={onSource}
                      />
                    </td>
                    <td>
                      <button
                        className="icon-button"
                        aria-label={`Edit task ${item.id}`}
                        onClick={() => onEdit(item)}
                        disabled={job.provenance.sample}
                      >
                        <Pencil size={15} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="empty-note">No explicit action items were found.</p>
        )}
        <div className="table-footer">
          <Check size={13} /> Sources link to the transcript. Review the audio
          before relying on assignments.
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <span className="section-icon">
            <ArrowUpRight size={19} />
          </span>
          <h2>Topics &amp; takeaways</h2>
        </div>
        {report.topics.length ? (
          <div className="topics-grid">
            {report.topics.map((topic) => (
              <div className="topic" key={topic.id}>
                <h3>{topic.title}</h3>
                <ClaimList
                  items={topic.theses}
                  empty="No supported takeaways."
                  onSource={onSource}
                />
              </div>
            ))}
          </div>
        ) : (
          <p className="empty-note">No topics were identified.</p>
        )}
      </section>

      <div className="two-panels">
        <section className="panel">
          <div className="section-heading">
            <span className="section-icon">
              <CircleHelp size={18} />
            </span>
            <h2>Open questions</h2>
            <span className="count">{report.open_questions.length}</span>
          </div>
          <ClaimList
            items={report.open_questions}
            empty="No unresolved questions were found."
            onSource={onSource}
          />
        </section>
        <section className="panel">
          <div className="section-heading">
            <span className="section-icon amber">
              <Flag size={17} />
            </span>
            <h2>Risks &amp; blockers</h2>
            <span className="count">{report.risks.length}</span>
          </div>
          <ClaimList
            items={report.risks}
            empty="No explicit risks or blockers were found."
            onSource={onSource}
          />
        </section>
      </div>
    </div>
  );
}
