import { useRef, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  AudioLines,
  FileAudio,
  Mic,
  Upload,
  X,
} from "lucide-react";
import type { Health } from "../types";
import { Recorder } from "./Recorder";

export function UploadView({
  health,
  submitting,
  onUpload,
  onExample,
  initialMode = "upload",
}: {
  health: Health | null;
  submitting: boolean;
  onUpload: (
    file: File,
    meetingDate: string,
    language: string,
    spokenLanguage?: string,
  ) => void;
  onExample: () => void;
  initialMode?: "upload" | "record";
}) {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState(initialMode);
  const [recording, setRecording] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [meetingDate, setMeetingDate] = useState("");
  const [language, setLanguage] = useState("ru");
  const [spokenLanguage, setSpokenLanguage] = useState("auto");
  function choose(candidate: File | undefined) {
    if (!candidate || submitting) return;
    setError("");
    setFile(null);
    if (!/\.(mp3|wav|m4a)$/i.test(candidate.name)) {
      setError("Choose an MP3, WAV, or M4A recording.");
      return;
    }
    if (!candidate.size) {
      setError("This recording is empty. Choose a file with audio.");
      return;
    }
    if (candidate.size > (health?.max_upload_mb ?? 100) * 1024 * 1024) {
      setError("This recording exceeds the upload size limit.");
      return;
    }
    setFile(candidate);
  }
  return (
    <div className="capture-view">
      <a className="back-link" href="#/workspace">
        <ArrowLeft size={14} /> All meetings
      </a>
      <div className="capture-heading">
        <h1>New meeting</h1>
      </div>
      <div className="capture-layout">
        <form
          className="upload-card"
          onSubmit={(e) => {
            e.preventDefault();
            if (
              file &&
              !recording &&
              !submitting &&
              health?.ready &&
              !health.busy
            )
              if (spokenLanguage === "auto")
                onUpload(file, meetingDate, language);
              else onUpload(file, meetingDate, language, spokenLanguage);
          }}
        >
          <div
            className="capture-tabs"
            role="group"
            aria-label="Meeting input method"
          >
            <button
              type="button"
              aria-pressed={mode === "record"}
              disabled={
                recording || submitting || (mode === "upload" && !!file)
              }
              onClick={() => {
                if (mode === "record") return;
                setMode("record");
                setFile(null);
                setError("");
              }}
            >
              <Mic size={16} /> Record a meeting
            </button>
            <button
              type="button"
              aria-pressed={mode === "upload"}
              disabled={
                recording || submitting || (mode === "record" && !!file)
              }
              onClick={() => {
                if (mode === "upload") return;
                setMode("upload");
                setFile(null);
                setError("");
              }}
            >
              <Upload size={16} /> Upload audio
            </button>
          </div>
          {mode === "record" ? (
            <Recorder
              maxSeconds={health?.max_duration_sec ?? 1800}
              maxBytes={(health?.max_upload_mb ?? 100) * 1024 * 1024}
              disabled={submitting}
              onRecording={setRecording}
              onFile={setFile}
              onDate={setMeetingDate}
            />
          ) : (
            <div
              className={`dropzone ${dragging ? "dragging" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                if (!submitting) setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                choose(e.dataTransfer.files[0]);
              }}
            >
              <input
                ref={input}
                className="sr-only"
                type="file"
                accept=".mp3,.wav,.m4a"
                aria-label="Meeting recording"
                disabled={submitting}
                onChange={(e) => {
                  choose(e.target.files?.[0]);
                  e.target.value = "";
                }}
              />
              {file ? (
                <>
                  <div className="upload-icon selected">
                    <FileAudio size={29} />
                  </div>
                  <h2 className="file-name">{file.name}</h2>
                  <p>
                    {(file.size / 1024 / 1024).toFixed(1)} MB · Ready to upload
                  </p>
                  <button
                    type="button"
                    className="text-button"
                    disabled={submitting}
                    onClick={() => setFile(null)}
                  >
                    <X size={13} /> Choose a different file
                  </button>
                </>
              ) : (
                <>
                  <div className="upload-icon">
                    <Upload size={29} strokeWidth={1.5} />
                  </div>
                  <h2>Drop your meeting recording here</h2>
                  <p>
                    MP3, WAV, or M4A · up to {health?.max_upload_mb ?? 100} MB
                  </p>
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => input.current?.click()}
                  >
                    Browse files <ArrowRight size={15} />
                  </button>
                  <small>
                    Up to {Math.floor((health?.max_duration_sec ?? 1800) / 60)}{" "}
                    minutes per recording
                  </small>
                </>
              )}
            </div>
          )}
          <div className="capture-options">
            <label className="spoken-language">
              Spoken language
              <select
                value={spokenLanguage}
                onChange={(event) => setSpokenLanguage(event.target.value)}
                disabled={submitting}
              >
                <option value="auto">Detect automatically</option>
                <option value="ru">Русский</option>
                <option value="kk">Қазақша</option>
                <option value="en">English</option>
              </select>
            </label>
            <p className="field-hint">
              For Kazakh with Russian words, try Қазақша if automatic detection
              chooses the wrong language.
            </p>
            <div className="upload-options">
              <label>
                Meeting date{" "}
                <span className="muted">
                  {mode === "record" && meetingDate
                    ? "recording date"
                    : "optional"}
                </span>
                <input
                  type="date"
                  value={meetingDate}
                  disabled={submitting}
                  onChange={(e) => setMeetingDate(e.target.value)}
                />
              </label>
              <label>
                Report language
                <select
                  value={language}
                  disabled={submitting}
                  onChange={(e) => setLanguage(e.target.value)}
                >
                  <option value="ru">Русский</option>
                  <option value="kk">Қазақша</option>
                  <option value="en">English</option>
                </select>
              </label>
            </div>
            <p className="field-hint">
              A meeting date helps resolve deadlines such as “tomorrow.”
            </p>
            {error && (
              <p role="alert" className="form-error">
                {error}
              </p>
            )}
            <button
              className="primary-button upload-submit"
              disabled={
                !file ||
                recording ||
                submitting ||
                !health?.ready ||
                health.busy
              }
              type="submit"
            >
              <AudioLines size={17} />
              {submitting
                ? "Uploading…"
                : health?.busy
                  ? "Processing another request…"
                  : "Create meeting report"}
              <ArrowRight size={16} />
            </button>
            {!health ? (
              <p className="setup-hint">
                Recording and file selection are available. Check the processing
                indicator above before creating a report.
              </p>
            ) : (
              !health.ready && (
                <p className="setup-hint">
                  Megan isn’t ready to create reports. Click{" "}
                  <strong>Local processing</strong> above to see what needs
                  attention.
                </p>
              )
            )}
          </div>
        </form>
      </div>
      <button className="example-button" onClick={onExample}>
        View sample report
        <ArrowRight size={16} />
      </button>
    </div>
  );
}
