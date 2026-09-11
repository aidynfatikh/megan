import { ArrowLeft } from "lucide-react";

export function MeetingListSkeleton({
  compact = false,
  label = "Loading meetings",
}: {
  compact?: boolean;
  label?: string;
}) {
  return (
    <div
      className={`meeting-list-skeleton ${compact ? "is-compact" : ""}`}
      role="status"
      aria-label={label}
      aria-busy="true"
    >
      <div aria-hidden="true">
        {[0, 1, 2].map((row) => (
          <div className="skeleton-meeting-row" key={row}>
            <span className="skeleton-block skeleton-file" />
            <div className="skeleton-lines">
              <span className="skeleton-block skeleton-row-title" />
              <span className="skeleton-block skeleton-row-meta" />
            </div>
            {!compact && <span className="skeleton-block skeleton-row-badge" />}
          </div>
        ))}
      </div>
      <span className="sr-only">{label}</span>
    </div>
  );
}

export function MeetingSkeleton() {
  return (
    <div className="meeting-skeleton">
      <a className="back-link" href="#/workspace">
        <ArrowLeft size={14} /> All meetings
      </a>
      <div role="status" aria-label="Loading meeting" aria-busy="true">
        <div aria-hidden="true">
          <div className="skeleton-meeting-heading">
            <span className="skeleton-block skeleton-heading" />
            <span className="skeleton-block skeleton-metadata" />
          </div>
          <div className="skeleton-audio-bar">
            <span className="skeleton-block skeleton-file" />
            <div className="skeleton-lines">
              <span className="skeleton-block skeleton-row-title" />
              <span className="skeleton-block skeleton-row-meta" />
            </div>
          </div>
          <div className="skeleton-report-tabs">
            <span className="skeleton-block" />
            <span className="skeleton-block" />
          </div>
          {[0, 1].map((section) => (
            <div className="skeleton-report-card" key={section}>
              <span className="skeleton-block skeleton-section-title" />
              <span className="skeleton-block" />
              <span className="skeleton-block" />
              <span className="skeleton-block skeleton-paragraph-end" />
            </div>
          ))}
        </div>
        <span className="sr-only">Loading meeting</span>
      </div>
    </div>
  );
}
