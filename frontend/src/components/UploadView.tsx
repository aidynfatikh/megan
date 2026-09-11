import { useRef, useState } from "react";
import {
  ArrowRight,
  AudioLines,
  FileAudio,
  ShieldCheck,
  Upload,
  X,
} from "lucide-react";
import type { Health } from "../types";

export function UploadView({
  health,
  submitting,
  onUpload,
  onExample,
}: {
  health: Health | null;
  submitting: boolean;
  onUpload: (file: File, meetingDate: string, language: string) => void;
  onExample: () => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const [meetingDate, setMeetingDate] = useState("");
  const [language, setLanguage] = useState("ru");

  function choose(candidate: File | undefined) {
    setError("");
    if (!candidate) return;
    if (!/\.(mp3|wav|m4a)$/i.test(candidate.name)) {
      setError("Choose an MP3, WAV, or M4A recording.");
      return;
    }
    if (candidate.size > (health?.max_upload_mb ?? 100) * 1024 * 1024) {
      setError("This recording exceeds the upload size limit.");
      return;
    }
    setFile(candidate);
  }

  return (
    <div className="upload-view">
      <div className="intro-tag">
        <span /> YOUR PRIVATE MEETING WORKSPACE
      </div>
      <h1>
        A conversation.
        <br />
        <span>A clear way forward.</span>
      </h1>
      <p className="intro-description">
        Turn meeting recordings into decisions, next steps,
        <br className="desktop-break" /> and a report you can trace back to the
        conversation.
      </p>
      <form
        className="upload-card"
        onSubmit={(e) => {
          e.preventDefault();
          if (file) onUpload(file, meetingDate, language);
        }}
      >
        <div
          className={`dropzone ${dragging ? "dragging" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
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
            onChange={(e) => choose(e.target.files?.[0])}
          />
          {file ? (
            <>
              <div className="upload-icon selected">
                <FileAudio size={27} />
              </div>
              <h2 className="file-name">{file.name}</h2>
              <p>{(file.size / 1024 / 1024).toFixed(1)} MB · Ready to upload</p>
              <button
                type="button"
                className="text-button"
                onClick={() => {
                  setFile(null);
                  if (input.current) input.current.value = "";
                }}
              >
                <X size={13} /> Choose a different file
              </button>
            </>
          ) : (
            <>
              <div className="upload-icon">
                <Upload size={27} strokeWidth={1.5} />
              </div>
              <h2>Drop your meeting recording here</h2>
              <p>MP3, WAV, or M4A · up to {health?.max_upload_mb ?? 100} MB</p>
              <button
                type="button"
                className="secondary-button"
                onClick={() => input.current?.click()}
              >
                Browse files <ArrowRight size={15} />
              </button>
            </>
          )}
        </div>
        <div className="upload-options">
          <label>
            Meeting date <span className="muted">optional</span>
            <input
              type="date"
              value={meetingDate}
              onChange={(e) => setMeetingDate(e.target.value)}
            />
          </label>
          <label>
            Report language
            <select
              value={language}
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
          disabled={!file || submitting || !health?.ready || health.busy}
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
        {health && !health.ready && (
          <p className="setup-hint">
            Local services need setup. Open <strong>System status</strong> or
            explore the example below.
          </p>
        )}
      </form>
      <button className="example-button" onClick={onExample}>
        Take a look around <span>Open an example report</span>
        <ArrowRight size={16} />
      </button>
      <div className="privacy-note">
        <ShieldCheck size={15} />
        <span>Your recordings and models stay on this device.</span>
      </div>
      <div className="workflow-hints">
        <div>
          <span>01</span>
          <strong>Capture the context</strong>
          <p>Bring your recording, in its original language.</p>
        </div>
        <div>
          <span>02</span>
          <strong>Find the next step</strong>
          <p>Decisions, owners, and deadlines in one place.</p>
        </div>
        <div>
          <span>03</span>
          <strong>Go back to the source</strong>
          <p>Check a quote. Listen. Export your report.</p>
        </div>
      </div>
    </div>
  );
}
