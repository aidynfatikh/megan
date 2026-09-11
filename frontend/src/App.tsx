import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  AudioLines,
  CalendarDays,
  Check,
  ChevronRight,
  Clock3,
  FileText,
  FolderOpen,
  HelpCircle,
  LoaderCircle,
  LockKeyhole,
  MessageSquare,
  Plus,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  X,
} from "lucide-react";
import { api, formatDate, timestamp } from "./api";
import type { Action, Answer, Health, Job, Source } from "./types";
import { ReportView } from "./components/ReportView";
import { UploadView } from "./components/UploadView";
import { EditTask } from "./components/EditTask";
import { Transcript } from "./components/Transcript";

const stages = ["decode", "transcribe", "analyze", "check_sources"];
const stageLabels: Record<string, string> = {
  queued: "Getting ready",
  decode: "Preparing audio",
  release_models: "Preparing local models",
  transcribe: "Transcribing the conversation",
  transcript_ready: "Saving the transcript",
  diarize: "Separating speakers",
  analyze: "Finding decisions and next steps",
  check_sources: "Checking source references",
  persist: "Saving your report",
  done: "Ready to review",
};

export default function App() {
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
  const running = !!job && ["queued", "running"].includes(job.status);
  const sample = !!job?.provenance.sample;

  useEffect(() => {
    const controller = new AbortController();
    async function refresh() {
      const results = await Promise.allSettled([
        api.health(controller.signal),
        api.jobs(controller.signal),
      ]);
      if (controller.signal.aborted) return;
      if (results[0].status === "fulfilled") {
        setHealth(results[0].value);
        setError((previous) =>
          previous ===
          "Cannot reach the local API. Start Megan and refresh this page."
            ? ""
            : previous,
        );
      } else
        setError(
          "Cannot reach the local API. Start Megan and refresh this page.",
        );
      if (results[1].status === "fulfilled") setHistory(results[1].value);
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
        if (!controller.signal.aborted) {
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

  function selectJob(next: Job | null) {
    setJob(next);
    setSource(null);
    setEditing(null);
    setTab("report");
    setAnswer(null);
    setError("");
    setCurrentTime(0);
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
        behavior: "smooth",
      }),
    );
  }

  async function openExample() {
    try {
      selectJob(await api.example());
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function upload(file: File, meetingDate: string, language: string) {
    setSubmitting(true);
    setError("");
    try {
      const next = await api.upload(file, meetingDate, language);
      selectJob(next);
      setHistory((previous) => [next, ...previous]);
      setClock(Date.now());
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  function updateJob(next: Job) {
    setJob(next);
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
    <div className="app-shell">
      <aside className="sidebar">
        <button
          className="brand"
          onClick={() => selectJob(null)}
          aria-label="Megan home"
        >
          <span className="brand-symbol">
            <AudioLines size={24} />
          </span>
          megan<span className="brand-period">.</span>
        </button>
        <div className="workspace-switch">
          <div className="workspace-avatar">M</div>
          <div>
            <strong>My workspace</strong>
            <span>Local workspace</span>
          </div>
          <LockKeyhole size={13} />
        </div>
        <button className="new-meeting" onClick={() => selectJob(null)}>
          <Plus size={17} />
          New meeting<span>＋</span>
        </button>
        <div className="sidebar-label">WORKSPACE</div>
        <button className="nav-item active" onClick={() => selectJob(null)}>
          <FolderOpen size={17} />
          All meetings<span className="nav-count">{history.length}</span>
        </button>
        <div className="sidebar-label recent-label">RECENT MEETINGS</div>
        <div className="history-list">
          {filteredHistory.length ? (
            filteredHistory.map((entry) => (
              <button
                key={entry.id}
                className={`history-item ${job?.id === entry.id ? "selected" : ""}`}
                onClick={async () => {
                  try {
                    selectJob(await api.job(entry.id));
                  } catch (err) {
                    setError((err as Error).message);
                  }
                }}
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
              {query
                ? "No matching meetings."
                : "Your conversations will find a home here."}
            </p>
          )}
        </div>
        <div className="sidebar-bottom">
          <div className="local-card">
            <ShieldCheck size={19} />
            <strong>Made to stay local</strong>
            <p>
              Your conversation.
              <br />
              Your device. Your control.
            </p>
          </div>
          <button className="nav-item" onClick={() => setHelpOpen(!helpOpen)}>
            <HelpCircle size={16} />
            How it works
          </button>
          <button
            className="nav-item"
            onClick={() => setStatusOpen(!statusOpen)}
          >
            <Settings2 size={16} />
            System status
            <span className={`status-dot ${health?.ready ? "ready" : ""}`} />
          </button>
          <div className="sidebar-profile">
            <span className="avatar">Y</span>
            <span>
              Your workspace<small>On this device</small>
            </span>
            <span className="version">v0.1</span>
          </div>
        </div>
      </aside>

      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace
            <ChevronRight size={13} />
            <span>Meetings</span>
          </div>
          <div className="topbar-actions">
            <label className="search-field">
              <Search size={15} />
              <input
                placeholder="Find a meeting…"
                aria-label="Search meetings"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>
            <span className="local-badge">
              <span />
              Local processing
            </span>
          </div>
        </header>
        <main className={`main-content ${job ? "has-meeting" : ""}`}>
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
                Run the setup and preflight commands in the README for missing
                services.
              </p>
            </section>
          )}
          {helpOpen && (
            <section className="panel help-panel">
              <div className="section-heading">
                <h2>From conversation to clarity</h2>
                <button
                  className="icon-button section-meta"
                  aria-label="Close help"
                  onClick={() => setHelpOpen(false)}
                >
                  <X size={17} />
                </button>
              </div>
              <p>
                Upload a recording and optionally provide its meeting date.
                Local models transcribe the audio and organize the outcomes.
                Click any source timestamp to check the original words, edit a
                task when needed, and export your report.
              </p>
              <p className="muted">
                Source matching checks quotations in the transcript. It does not
                guarantee that recognition or interpretation is correct. Your
                review matters.
              </p>
            </section>
          )}

          {!job ? (
            <UploadView
              health={health}
              submitting={submitting}
              onUpload={upload}
              onExample={() => void openExample()}
            />
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
                  <button onClick={() => selectJob(null)}>
                    Use your recording <ArrowRight size={14} />
                  </button>
                </div>
              )}
              <div className="meeting-heading">
                <div>
                  <div className="eyebrow">MEETING NOTES</div>
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
                        : `Processed in ${elapsed.toFixed(1)}s · ${job.segments.length} transcript segments`}
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
                  <span className="recording-private">
                    <LockKeyhole size={13} />
                    On-device
                  </span>
                </div>
              )}

              {running && (
                <section className="panel processing-panel" aria-live="polite">
                  <div className="processing-title">
                    <LoaderCircle className="spin" size={24} />
                    <div>
                      <h2>{stageLabels[job.stage] ?? job.stage}</h2>
                      <p>
                        The models work one at a time. Your report will appear
                        here.
                      </p>
                    </div>
                    <span className="elapsed">{timestamp(elapsed)}</span>
                  </div>
                  <div className="stage-track">
                    {stages.map((s, i) => {
                      const stage =
                        job.stage === "release_models"
                          ? "transcribe"
                          : ["transcript_ready", "diarize"].includes(job.stage)
                            ? "analyze"
                            : job.stage;
                      const current = stages.indexOf(stage);
                      return (
                        <div
                          key={s}
                          className={
                            i < current
                              ? "complete"
                              : i === current
                                ? "current"
                                : ""
                          }
                        >
                          <span>
                            {i < current ? <Check size={13} /> : i + 1}
                          </span>
                          {
                            [
                              "Prepare",
                              "Transcribe",
                              "Analyze",
                              "Check sources",
                            ][i]
                          }
                        </div>
                      );
                    })}
                  </div>
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
                    <div className="tab-note">
                      <LockKeyhole size={12} />
                      {sample ? "Illustrative preview" : "Saved on this device"}
                    </div>
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
                          <span className="eyebrow">BACK TO THE SOURCE</span>
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

              {report && !sample && health?.chat_enabled && (
                <section className="panel chat-panel">
                  <div className="section-heading">
                    <span className="section-icon">
                      <MessageSquare size={18} />
                    </span>
                    <h2>Ask this meeting</h2>
                    <span className="section-meta muted">
                      Answers with sources
                    </span>
                  </div>
                  <form
                    onSubmit={async (e) => {
                      e.preventDefault();
                      if (!question.trim()) return;
                      setAsking(true);
                      try {
                        setAnswer(await api.chat(job.id, question.trim()));
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
                      disabled={!question.trim() || asking || running}
                      aria-label="Ask meeting"
                    >
                      {asking ? (
                        <LoaderCircle className="spin" size={17} />
                      ) : (
                        <Send size={16} />
                      )}
                    </button>
                  </form>
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
        <footer className="page-footer">
          <span>
            megan<span className="brand-period">.</span>{" "}
            <span className="muted">Less note-taking. More being there.</span>
          </span>
          <span>
            <ShieldCheck size={13} />
            Built for private conversations
          </span>
        </footer>
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
