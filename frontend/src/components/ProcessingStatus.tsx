import { useEffect, useId, useRef, useState } from "react";
import { Check, ChevronDown, RefreshCw, X } from "lucide-react";
import type { Health } from "../types";

function processingIssues(health: Health | null): string[] {
  if (!health)
    return [
      "Megan isn’t running or can’t be reached. Start Megan on this computer, then check again.",
    ];
  const issues: string[] = [];
  if (!health.database)
    issues.push(
      "Meeting storage is unavailable. Restart Megan so your meetings can be saved and opened.",
    );
  if (!health.ffmpeg)
    issues.push(
      "The audio tools are missing. Complete Megan’s setup to read recordings.",
    );
  if (!health.asr)
    issues.push(
      "Speech recognition isn’t ready. Complete Megan’s model setup to turn audio into text.",
    );
  if (!health.ollama)
    issues.push(
      "The report generator isn’t ready. Open Ollama and make sure Megan’s model is installed.",
    );
  if (health.diarization !== "none" && !health.diarization_ready)
    issues.push(
      health.ready
        ? "Speaker labels are unavailable. You can still create reports; complete the speaker setup to tell voices apart."
        : "Speaker labels are unavailable. Complete the speaker setup to tell voices apart.",
    );
  if (!health.ready && !issues.length)
    issues.push(
      "Megan isn’t ready to process recordings. Restart Megan, then check again.",
    );
  return issues;
}

export function ProcessingStatus({
  health,
  checking,
  hasChecked,
  onRefresh,
}: {
  health: Health | null;
  checking: boolean;
  hasChecked: boolean;
  onRefresh: () => void;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLElement>(null);
  const id = useId();
  const issues = hasChecked ? processingIssues(health) : [];
  const state = !hasChecked ? "checking" : issues.length ? "error" : "ready";
  const label =
    state === "checking"
      ? "Checking"
      : state === "error"
        ? "Needs attention"
        : "Ready";

  useEffect(() => {
    if (!open) return;
    panel.current?.focus();
    function outside(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    function keyboard(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
        trigger.current?.focus();
      }
    }
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", keyboard);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", keyboard);
    };
  }, [open]);

  return (
    <div
      className="processing-status"
      ref={root}
      onBlur={(event) => {
        if (
          event.relatedTarget &&
          !event.currentTarget.contains(event.relatedTarget)
        )
          setOpen(false);
      }}
    >
      <button
        ref={trigger}
        className={`processing-status-trigger is-${state}`}
        aria-label={`Local processing: ${label}`}
        aria-expanded={open}
        aria-controls={open ? id : undefined}
        aria-haspopup="dialog"
        title={`Local processing: ${label}`}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="processing-status-dot" aria-hidden="true" />
        <span className="processing-status-label">Local processing</span>
        <ChevronDown size={13} aria-hidden="true" />
      </button>
      {open && (
        <section
          ref={panel}
          id={id}
          role="dialog"
          aria-labelledby={`${id}-title`}
          tabIndex={-1}
          className="processing-status-popover"
        >
          <div className="processing-status-heading">
            <h2 id={`${id}-title`}>
              {state === "checking"
                ? "Checking Megan…"
                : issues.length
                  ? "Something needs attention"
                  : "Everything is ready"}
            </h2>
            <button
              className="icon-button"
              aria-label="Close processing status"
              onClick={() => {
                setOpen(false);
                trigger.current?.focus();
              }}
            >
              <X size={17} />
            </button>
          </div>
          <div aria-live="polite">
            {issues.length ? (
              <ul>
                {issues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            ) : (
              <p>
                {hasChecked ? (
                  <>
                    <Check size={16} aria-hidden="true" /> You can record a
                    meeting or upload audio.
                  </>
                ) : (
                  "Checking what Megan needs to process your meetings."
                )}
              </p>
            )}
            {health?.busy && (
              <p>
                Megan is working on another request. You can create your next
                report when it finishes.
              </p>
            )}
          </div>
          <button
            className="processing-status-refresh"
            onClick={onRefresh}
            disabled={checking}
          >
            <RefreshCw
              size={14}
              className={checking ? "spin" : undefined}
              aria-hidden="true"
            />
            {checking ? "Checking…" : "Check again"}
          </button>
        </section>
      )}
    </div>
  );
}
