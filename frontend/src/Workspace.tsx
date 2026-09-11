import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  AudioLines,
  CalendarDays,
  ChevronRight,
  Clock3,
  FileText,
  FolderOpen,
  HelpCircle,
  LoaderCircle,
  MessageSquare,
  Plus,
  ListTodo,
  Menu,
  Send,
  Settings2,
  X,
} from "lucide-react";
import { api, formatDate, timestamp } from "./api";
import type { Action, Answer, Health, Job, Source } from "./types";
import { ReportView } from "./components/ReportView";
import { UploadView } from "./components/UploadView";
import { EditTask } from "./components/EditTask";
import { Transcript } from "./components/Transcript";
import { ProcessingStages } from "./components/ProcessingStages";
import { Dashboard } from "./components/Dashboard";
import { Brand } from "./components/Brand";
import { navigate, protectCapture } from "./navigation";

const stageLabels: Record<string, string> = {
  queued: "Getting ready",
  decode: "Preparing audio",
  release_models: "Preparing local models",
  transcribe: "Transcribing the conversation",
  transcript_ready: "Saving the transcript",
  diarize: "Separating speakers",
  speakers_ready: "Saving speaker labels",
  analyze: "Finding decisions and next steps",
  check_sources: "Checking source references",
  persist: "Saving your report",
  done: "Ready to review",
};

export default function Workspace({ route }: { route: string }) {
  const [loading, setLoading] = useState(true);
  const [loadingJob, setLoadingJob] = useState(false);
  const [mobileMenu, setMobileMenu] = useState(false);
  const activeJobId = useRef<string | null>(null);
  const sidebar = useRef<HTMLElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [history, setHistory] = useState<Job[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState<"report" | "transcript">("report");
  const [statusOpen, setStatusOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [source, setSource] = useState<Source | null>(null);
  const [editing, setEditing] = useState<Action | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [clock, setClock] = useState(Date.now());
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [asking, setAsking] = useState(false);
  const audio = useRef<HTMLAudioElement>(null);
  const sourcePanel = useRef<HTMLElement>(null);
  const pollingFailure = useRef(false);
  const running =
    !!job &&
    route === `/meetings/${job.id}` &&
    ["queued", "running"].includes(job.status);
  const sample = !!job?.provenance.sample;

  useEffect(() => {
    const controller = new AbortController();
    let refreshing = false;
    async function refresh() {
      if (refreshing) return;
      refreshing = true;
      const results = await Promise.allSettled([
        api.health(controller.signal),
        api.jobs(controller.signal),
      ]);
      refreshing = false;
      if (controller.signal.aborted) return;
      setLoading(false);
      if (results[0].status === "fulfilled") {
        setHealth(results[0].value);
        setError((previous) =>
          previous ===
          "Cannot reach the local API. Start Megan and refresh this page."
            ? ""
            : previous,
        );
      } else {
        setHealth(null);
        setError(
          "Cannot reach the local API. Start Megan and refresh this page.",
        );
      }
      if (results[1].status === "fulfilled") {
        setHistory(results[1].value);
        setError((previous) =>
          previous ===
          "Couldn’t load your meetings. Check System status; we’ll try again shortly."
            ? ""
            : previous,
        );
      } else if (results[0].status === "fulfilled")
        setError(
          "Couldn’t load your meetings. Check System status; we’ll try again shortly.",
        );
    }
    void refresh();
    const interval = setInterval(() => void refresh(), 10000);
    return () => {
      controller.abort();
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    if (!job || !running) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const id = job.id;
    async function poll() {
      try {
        const updated = await api.job(id, controller.signal);
        if (!controller.signal.aborted && activeJobId.current === id) {
          setJob(updated);
          setHistory((previous) => [
            updated,
            ...previous.filter((j) => j.id !== updated.id),
          ]);
          if (pollingFailure.current) {
            setError("");
            pollingFailure.current = false;
          }
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          pollingFailure.current = true;
          setError((err as Error).message);
        }
      }
      if (!controller.signal.aborted)
        timer = setTimeout(() => void poll(), 1000);
    }
    void poll();
    const ticker = setInterval(() => setClock(Date.now()), 1000);
    return () => {
      controller.abort();
      clearTimeout(timer);
      clearInterval(ticker);
    };
  }, [job?.id, running]);

  useEffect(() => {
    const controller = new AbortController();
    setMobileMenu(false);
    setSource(null);
    setEditing(null);
    setAnswer(null);
    setQuestion("");
    setCurrentTime(0);
    setTab("report");
    setError("");
    const id = route.startsWith("/meetings/")
      ? route.slice("/meetings/".length)
      : null;
    activeJobId.current = id;
    if (id || route === "/example") {
      setJob(null);
      setLoadingJob(true);
      const request = id
        ? api.job(id, controller.signal)
        : api.example(controller.signal);
      void request
        .then((next) => {
          if (!controller.signal.aborted) setJob(next);
        })
        .catch((err) => {
          if (!controller.signal.aborted) {
            setJob(null);
            setError((err as Error).message);
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoadingJob(false);
        });
    } else {
      setJob(null);
      setLoadingJob(false);
    }
    return () => controller.abort();
  }, [route]);

  function goTo(path: string) {
    setMobileMenu(false);
    navigate(path);
  }

  useEffect(() => {
    if (!mobileMenu) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusables = () =>
      Array.from(
        sidebar.current?.querySelectorAll<HTMLElement>(
          "a[href], button:not(:disabled), input, select",
        ) ?? [],
      );
    focusables()[0]?.focus();
    function keyboard(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMobileMenu(false);
        return;
      }
      if (event.key !== "Tab") return;
      const targets = focusables();
      const first = targets[0];
      const last = targets[targets.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    }
    document.addEventListener("keydown", keyboard);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", keyboard);
      menuButton.current?.focus();
    };
  }, [mobileMenu]);

  function selectJob(next: Job | null) {
    setJob(next);
    setSource(null);
    setEditing(null);
    setTab("report");
    setAnswer(null);
    setQuestion("");
    setError("");
    setCurrentTime(0);
    goTo(next ? `/meetings/${next.id}` : "/workspace");
  }

  function viewSource(next: Source) {
    setSource(next);
    if (audio.current && next.start != null && !sample) {
      audio.current.currentTime = next.start;
      void audio.current
        .play()
        .catch(() => setError("Press play to listen to the selected source."));
    }
    requestAnimationFrame(() =>
      sourcePanel.current?.scrollIntoView({
        block: "nearest",
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "auto"
          : "smooth",
      }),
    );
  }

  function openExample() {
    goTo("/example");
  }

  async function upload(file: File, meetingDate: string, language: string) {
    const uploadRoute = window.location.hash;
    setSubmitting(true);
    setError("");
    try {
      const next = await api.upload(file, meetingDate, language);
      protectCapture(false);
      if (window.location.hash === uploadRoute) selectJob(next);
      setHistory((previous) => [next, ...previous]);
      setClock(Date.now());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  function updateJob(next: Job) {
    if (activeJobId.current === next.id) setJob(next);
    setHistory((previous) =>
      previous.map((j) => (j.id === next.id ? next : j)),
    );
  }
  const filteredHistory = history.filter((j) =>
    `${j.filename} ${j.report?.title ?? ""}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  const elapsed =
    running && job
      ? job.elapsed_sec +
        Math.max(0, (clock - new Date(job.updated_at).getTime()) / 1000)
      : (job?.elapsed_sec ?? 0);
  const report = job?.report;

  return (
    <div className={`app-shell ${mobileMenu ? "menu-is-open" : ""}`}>
      <a
        className="skip-link"
        href="#workspace-main"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("workspace-main")?.focus();
        }}
      >
        Skip to content
      </a>
      {mobileMenu && (
        <button
          className="sidebar-scrim"
          aria-label="Close navigation"
          onClick={() => setMobileMenu(false)}
        />
      )}
      <aside
        ref={sidebar}
        className="sidebar"
        role={mobileMenu ? "dialog" : undefined}
        aria-modal={mobileMenu || undefined}
        aria-label="Workspace navigation"
      >
        {mobileMenu && (
          <button
            className="sidebar-close icon-button"
            aria-label="Close navigation menu"
            onClick={() => setMobileMenu(false)}
          >
            <X size={20} />
          </button>
        )}
        <a className="brand" href="#" aria-label="Megan home">
          <Brand />
        </a>
        <button className="new-meeting" onClick={() => goTo("/new/record")}>
          <Plus size={17} />
          New meeting
        </button>
        <button
          className={`nav-item ${route !== "/actions" ? "active" : ""}`}
          onClick={() => goTo("/workspace")}
        >
          <FolderOpen size={17} />
          All meetings<span className="nav-count">{history.length}</span>
        </button>
        <button
          className={`nav-item ${route === "/actions" ? "active" : ""}`}
          onClick={() => goTo("/actions")}
        >
          <ListTodo size={17} /> Action items
          <span className="nav-count">
            {history.reduce(
              (sum, entry) => sum + (entry.report?.action_items.length ?? 0),
              0,
            )}
          </span>
        </button>
        <div className="sidebar-label recent-label">RECENT MEETINGS</div>
        <div className="history-list">
          {filteredHistory.length ? (
            filteredHistory.slice(0, 6).map((entry) => (
              <button
                key={entry.id}
                className={`history-item ${job?.id === entry.id ? "selected" : ""}`}
                onClick={() => goTo(`/meetings/${entry.id}`)}
              >
                <FileText size={15} />
                <span>
                  <strong>{entry.report?.title ?? entry.filename}</strong>
                  <small>
                    {formatDate(entry.created_at)}
                    {entry.status !== "done" ? ` · ${entry.status}` : ""}
                  </small>
                </span>
              </button>
            ))
          ) : (
            <p className="history-empty">
              {query ? "No matching meetings." : "No meetings yet."}
            </p>
          )}
        </div>
        <div className="sidebar-bottom">
          <button
            className="nav-item"
            onClick={() => {
              setHelpOpen(!helpOpen);
              setStatusOpen(false);
              setMobileMenu(false);
            }}
          >
            <HelpCircle size={16} />
            How it works
          </button>
          <button
            className="nav-item"
            onClick={() => {
              setStatusOpen(!statusOpen);
              setHelpOpen(false);
              setMobileMenu(false);
            }}
          >
            <Settings2 size={16} />
            System status
            <span className={`status-dot ${health?.ready ? "ready" : ""}`} />
          </button>
        </div>
      </aside>

      <div className="main-shell" inert={mobileMenu}>
        <header className="topbar">
          <button
            ref={menuButton}
            className="workspace-menu icon-button"
            aria-label="Open navigation"
            aria-expanded={mobileMenu}
            onClick={() => setMobileMenu(!mobileMenu)}
          >
            <Menu size={21} />
          </button>
          <div className="breadcrumb">
            Workspace
            <ChevronRight size={13} />
            <span>
              {route === "/actions"
                ? "Action items"
                : route.startsWith("/new")
                  ? "New meeting"
                  : "Meetings"}
            </span>
          </div>
          <div className="topbar-actions">
            <a href="#/workspace" className="topbar-home">
              Your workspace <ArrowUpRight size={14} />
            </a>
            <span className="local-badge">
              <span />
              Local processing
            </span>
          </div>
        </header>
        <main
          id="workspace-main"
          tabIndex={-1}
          className={`main-content ${job ? "has-meeting" : ""}`}
        >
          {error && (
            <div className="notice error" role="alert">
              <AlertCircle size={17} />
              <span>{error}</span>
              <button
                className="icon-button"
                aria-label="Dismiss error"
                onClick={() => setError("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {statusOpen && (
            <section className="panel status-panel">
              <div className="section-heading">
                <h2>System status</h2>
                <button
                  className="icon-button section-meta"
                  aria-label="Close system status"
                  onClick={() => setStatusOpen(false)}
                >
                  <X size={17} />
                </button>
              </div>
              <div className="status-grid">
                {[
                  ["PostgreSQL", health?.database],
                  ["Audio tools", health?.ffmpeg],
                  ["Whisper weights", health?.asr],
                  ["Ollama model", health?.ollama],
                  ...(health && health.diarization !== "none"
                    ? [["Sortformer (optional)", health.diarization_ready]]
                    : []),
                ].map(([label, ready]) => (
                  <div key={String(label)}>
                    <span className={`status-dot ${ready ? "ready" : ""}`} />
                    <strong>{label}</strong>
                    <small>{ready ? "Available" : "Setup needed"}</small>
                  </div>
                ))}
              </div>
              <p className="muted">
                ASR: {health?.asr_backend ?? "—"} · LLM: {health?.llm ?? "—"}.
                {health?.diarization === "none"
                  ? " Speaker separation is disabled. "
                  : " "}
                Run the setup and preflight commands in the README for missing
                services.
              </p>
            </section>
          )}
          {helpOpen && (
            <section className="panel help-panel">
              <div className="section-heading">
                <h2>How it works</h2>
                <button
                  className="icon-button section-meta"
                  aria-label="Close help"
                  onClick={() => setHelpOpen(false)}
                >
                  <X size={17} />
                </button>
              </div>
              <p>
                Record your microphone or upload a recording and provide its
                meeting date when known. Local models transcribe the audio and
                organize the outcomes. Click any source timestamp to check the
                original words, edit a task when needed, and export your report.
              </p>
              <p className="muted">
                Source matching checks quotations in the transcript. It does not
                guarantee that recognition or interpretation is correct. Your
                review matters.
              </p>
            </section>
          )}

          {loadingJob ? (
            <div className="app-loading" role="status">
              <LoaderCircle className="spin" size={22} /> Opening your meeting…
            </div>
          ) : !job ? (
            route.startsWith("/new") ? (
              <UploadView
                key={route}
                initialMode={route === "/new/record" ? "record" : "upload"}
                health={health}
                submitting={submitting}
                onUpload={upload}
                onExample={openExample}
              />
            ) : (
              <Dashboard
                history={history}
                health={health}
                loading={loading}
                query={query}
                onQuery={setQuery}
                actionsOnly={route === "/actions"}
              />
            )
          ) : (
            <>
              <button className="back-link" onClick={() => selectJob(null)}>
                <ArrowLeft size={14} />
                All meetings
              </button>
              {sample && (
                <div className="example-banner">
                  <FileText size={15} />
                  <span>
                    <strong>Example report</strong> · Illustrative transcript,
                    no recorded audio or model run.
                  </span>
                  <button onClick={() => goTo("/new/upload")}>
                    Use your recording <ArrowRight size={14} />
                  </button>
                </div>
              )}
              <div className="meeting-heading">
                <div>
                  <h1>{report?.title ?? job.filename}</h1>
                  <div className="meeting-meta">
                    <span>
                      <CalendarDays size={14} />
                      {formatDate(job.meeting_date)}
                    </span>
                    {job.duration_sec != null && (
                      <span>
                        <Clock3 size={14} />
                        {timestamp(job.duration_sec)} recording
                      </span>
                    )}
                    <span>
                      <span
                        className={`status-dot ${job.status === "done" ? "ready" : ""}`}
                      />
                      {sample
                        ? "Example"
                        : job.status === "done"
                          ? "Ready to review"
                          : job.status}
                    </span>
                  </div>
                </div>
                {report && !sample && (
                  <div className="export-actions">
                    <a
                      className="secondary-button"
                      href={`/api/jobs/${job.id}/export?format=json`}
                      download
                    >
                      <ArrowDownToLine size={15} />
                      Export JSON
                    </a>
                    <details className="more-exports">
                      <summary aria-label="More export formats">
                        More
                        <ChevronRight size={14} />
                      </summary>
                      <div>
                        <a
                          href={`/api/jobs/${job.id}/export?format=csv`}
                          download
                        >
                          Task table (.csv)
                        </a>
                        <a
                          href={`/api/jobs/${job.id}/export?format=ics`}
                          download
                        >
                          Task deadlines (.ics)
                        </a>
                        <small>ICS includes resolved dates only.</small>
                      </div>
                    </details>
                  </div>
                )}
              </div>

              {!sample && (
                <div className="recording-bar">
                  <div className="recording-icon">
                    <AudioLines size={22} />
                  </div>
                  <div className="recording-info">
                    <strong>{job.filename}</strong>
                    <span>
                      {running
                        ? `${stageLabels[job.stage] ?? job.stage} · ${timestamp(elapsed)} elapsed`
                        : `${job.status === "done" ? "Processed" : "Stopped"} in ${elapsed.toFixed(1)}s · ${job.segments.length} transcript segments`}
                    </span>
                  </div>
                  <audio
                    ref={audio}
                    key={job.id}
                    controls
                    preload="metadata"
                    aria-label="Meeting audio player"
                    src={`/api/jobs/${job.id}/audio`}
                    onTimeUpdate={() =>
                      setCurrentTime(audio.current?.currentTime ?? 0)
                    }
                  />
                </div>
              )}

              {running && (
                <section className="panel processing-panel" aria-live="polite">
                  <div className="processing-title">
                    <LoaderCircle className="spin" size={24} />
                    <div>
                      <h2>{stageLabels[job.stage] ?? job.stage}</h2>
                      <p>
                        Your report will appear here when processing finishes.
                      </p>
                    </div>
                    <span className="elapsed">{timestamp(elapsed)}</span>
                  </div>
                  <ProcessingStages job={job} />
                </section>
              )}
              {job.error && (
                <section className="notice error">
                  <AlertCircle size={20} />
                  <div>
                    <strong>We couldn’t finish this recording</strong>
                    <p>{job.error.message}</p>
                  </div>
                  <button
                    className="secondary-button"
                    onClick={async () => {
                      try {
                        updateJob(await api.retry(job.id));
                        setClock(Date.now());
                      } catch (err) {
                        setError((err as Error).message);
                      }
                    }}
                  >
                    Retry processing
                  </button>
                </section>
              )}
              {job.warnings.map((warning, i) => (
                <div className="notice" key={i}>
                  <AlertCircle size={16} />
                  {warning}
                </div>
              ))}

              {(report || job.segments.length > 0) && (
                <>
                  <div className="meeting-tabs">
                    <button
                      className={tab === "report" ? "active" : ""}
                      onClick={() => setTab("report")}
                    >
                      <FileText size={16} />
                      Meeting report
                    </button>
                    <button
                      className={tab === "transcript" ? "active" : ""}
                      onClick={() => setTab("transcript")}
                    >
                      <AudioLines size={16} />
                      Transcript<span>{job.segments.length}</span>
                    </button>
                  </div>
                  <div
                    className={`review-layout ${source ? "with-source" : ""}`}
                  >
                    <div>
                      {tab === "report" ? (
                        <ReportView
                          job={job}
                          onSource={viewSource}
                          onEdit={setEditing}
                        />
                      ) : (
                        <Transcript
                          job={job}
                          currentTime={currentTime}
                          selected={source?.segment_id}
                          onSource={viewSource}
                          onRename={async (id, name) =>
                            updateJob(
                              await api.renameSpeaker(
                                job.id,
                                id,
                                name,
                                job.report_revision ?? 1,
                              ),
                            )
                          }
                        />
                      )}
                    </div>
                    {source && (
                      <aside className="source-panel panel" ref={sourcePanel}>
                        <div className="section-heading">
                          <span className="eyebrow">SOURCE</span>
                          <button
                            className="icon-button section-meta"
                            aria-label="Close source"
                            onClick={() => setSource(null)}
                          >
                            <X size={16} />
                          </button>
                        </div>
                        <div className="source-time">
                          <AudioLines size={20} />
                          {timestamp(source.start)}
                          <span>— {timestamp(source.end)}</span>
                        </div>
                        <blockquote>{source.quote}</blockquote>
                        <p className="muted">
                          {sample
                            ? "Illustrative quotation. Upload a recording to listen to its sources."
                            : "Listen to this passage to check the interpretation."}
                        </p>
                        <button
                          className="text-button"
                          onClick={() => setTab("transcript")}
                        >
                          See in transcript <ArrowRight size={14} />
                        </button>
                      </aside>
                    )}
                  </div>
                </>
              )}

              {report &&
                !sample &&
                job.segments.length > 0 &&
                health?.chat_enabled && (
                  <section className="panel chat-panel">
                    <div className="section-heading">
                      <span className="section-icon">
                        <MessageSquare size={18} />
                      </span>
                      <h2>Ask this meeting</h2>
                    </div>
                    <form
                      onSubmit={async (e) => {
                        e.preventDefault();
                        if (
                          !question.trim() ||
                          asking ||
                          running ||
                          health?.busy
                        )
                          return;
                        setAsking(true);
                        try {
                          const reply = await api.chat(job.id, question.trim());
                          if (activeJobId.current === job.id) setAnswer(reply);
                        } catch (err) {
                          setError((err as Error).message);
                        } finally {
                          setAsking(false);
                        }
                      }}
                    >
                      <input
                        aria-label="Question about this meeting"
                        placeholder="What did we agree about the launch?"
                        value={question}
                        maxLength={1000}
                        onChange={(e) => setQuestion(e.target.value)}
                      />
                      <button
                        className="primary-button"
                        disabled={
                          !question.trim() || asking || running || health?.busy
                        }
                        aria-label="Ask meeting"
                      >
                        {asking ? (
                          <LoaderCircle className="spin" size={17} />
                        ) : (
                          <Send size={16} />
                        )}
                      </button>
                    </form>
                    {(asking || health?.busy) && (
                      <p className="muted" role="status">
                        {asking
                          ? "Reading the transcript to find your answer…"
                          : "Megan is processing another request. You can ask your question when it finishes."}
                      </p>
                    )}
                    {answer && (
                      <div className="chat-answer">
                        <p>{answer.answer}</p>
                        {answer.citations.map((citation, i) => (
                          <button
                            className="source-button"
                            key={i}
                            onClick={() => viewSource(citation)}
                          >
                            {timestamp(citation.start)} · {citation.segment_id}
                          </button>
                        ))}
                        <small className="muted">
                          {answer.supported
                            ? "Quotation matched to the transcript; review its meaning in context."
                            : "No matching source was found."}
                        </small>
                      </div>
                    )}
                  </section>
                )}
            </>
          )}
        </main>
      </div>
      {editing && job && (
        <EditTask
          key={editing.id}
          item={editing}
          revision={job.report_revision ?? 1}
          onClose={() => setEditing(null)}
          onSave={async (patch) =>
            updateJob(await api.editAction(job.id, editing.id, patch))
          }
        />
      )}
    </div>
  );
}
