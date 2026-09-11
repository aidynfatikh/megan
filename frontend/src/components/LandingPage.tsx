import { useState } from "react";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  AudioLines,
  CheckCheck,
  ChevronDown,
  FileText,
  ListTodo,
  Menu,
  Mic,
  Play,
  Sparkles,
  X,
} from "lucide-react";
import { Brand } from "./Brand";

const outcomes = [
  {
    label: "Decisions",
    icon: CheckCheck,
    title: "See what was decided.",
    text: "Review the decisions separately from the discussion, with links to the original words.",
    detail: "Launch the pilot with the existing test group.",
    quote:
      "Let’s launch the pilot with the existing test group. We can expand after we’ve reviewed their feedback.",
    time: "12:42",
    speaker: "Maya",
    tag: "AGREED IN THE MEETING",
  },
  {
    label: "Next steps",
    icon: ListTodo,
    title: "Know who’s doing what.",
    text: "Review tasks, owners, and stated deadlines. Edit the details before exporting.",
    detail: "Maya · Prepare the release checklist · Friday",
    quote:
      "I’ll prepare the release checklist and have it ready by Friday, before we open the pilot.",
    time: "14:08",
    speaker: "Maya",
    tag: "CLEAR OWNERSHIP",
  },
  {
    label: "Sources",
    icon: AudioLines,
    title: "Check the original words.",
    text: "Follow a timestamp to read the transcript or listen to the recording.",
    detail: "Review feedback before expanding the pilot.",
    quote:
      "Let’s launch the pilot with the existing test group. We can expand after we’ve reviewed their feedback.",
    time: "12:42",
    speaker: "Maya",
    tag: "BACKED BY THE CONVERSATION",
  },
];

export function Waveform({ active = false }: { active?: boolean }) {
  return (
    <span className={`waveform ${active ? "active" : ""}`} aria-hidden="true">
      {Array.from({ length: 38 }, (_, i) => (
        <i
          key={i}
          style={{
            height: `${10 + ((i * 17 + i * i * 7) % 34)}px`,
            animationDelay: `${i * -0.07}s`,
          }}
        />
      ))}
    </span>
  );
}

function ReportPreview() {
  const [sourceOpen, setSourceOpen] = useState(false);
  return (
    <div className="hero-composition">
      <div className="collage-paper" aria-hidden="true">
        <svg viewBox="0 0 150 90" fill="none">
          <path
            d="M12 62C41 11 68 8 67 57s45 25 66-37M119 22l18-8-2 22"
            stroke="currentColor"
            strokeWidth="2"
          />
        </svg>
      </div>
      <div className="collage-stripes" aria-hidden="true" />
      <article className="preview-document">
        <div className="preview-window" aria-hidden="true">
          <span>
            <i />
            <i />
            <i />
          </span>
          <ArrowUpRight size={14} />
        </div>
        <div className="preview-content">
          <div className="preview-overline">
            <FileText size={14} /> EXAMPLE REPORT
          </div>
          <h2>Product sync</h2>
          <p className="preview-metadata">Friday, 11 September</p>
          <div className="preview-summary">
            <Sparkles size={16} />
            <p>
              Launch the pilot with the existing test group. Maya will prepare
              the release checklist by Friday.
            </p>
          </div>
          <div className="preview-section">
            <h3>
              <CheckCheck size={16} /> What we decided
            </h3>
            <p>
              Start with the existing test group, then expand based on feedback.
            </p>
            <button
              className={`source-button ${sourceOpen ? "selected" : ""}`}
              aria-expanded={sourceOpen}
              aria-controls="hero-source"
              onClick={() => setSourceOpen(!sourceOpen)}
            >
              <Play size={10} fill="currentColor" /> 12:42{" "}
              <span>View source</span>
            </button>
          </div>
          <div className="preview-section">
            <h3>
              <ListTodo size={16} /> What happens next
            </h3>
            <div className="preview-task">
              <span className="task-outline" />
              <span>
                Prepare the release checklist
                <small>
                  <span className="initial-avatar">M</span> Maya{" "}
                  <span className="due-chip">Friday</span>
                </small>
              </span>
            </div>
          </div>
        </div>
      </article>
      <div
        className={`floating-source ${sourceOpen ? "expanded" : ""}`}
        id="hero-source"
        aria-live="polite"
      >
        {sourceOpen ? (
          <>
            <span className="source-caption">
              <AudioLines size={15} /> MAYA · 12:42
            </span>
            <p>
              “Let’s launch the pilot with the existing test group. We can
              expand after we’ve reviewed their feedback.”
            </p>
            <small>Illustrative transcript · no audio</small>
          </>
        ) : (
          <Waveform />
        )}
      </div>
    </div>
  );
}

const faqs = [
  [
    "How do I bring a meeting into Megan?",
    "Record from your microphone in the workspace, or upload an MP3, WAV, or M4A. Browser recording captures your microphone, not the audio inside a meeting app. For remote calls, upload the recording from your meeting tool. Let participants know before recording.",
  ],
  [
    "Does my audio leave this device?",
    "In the local setup, audio, transcripts, reports, and model processing stay on the machine running Megan. Model files need to be downloaded during initial setup; everyday processing does not require a cloud AI service. Recordings and reports remain in local storage until you remove them from that machine.",
  ],
  [
    "Which languages can I use?",
    "Megan uses multilingual transcription and can produce reports in English, Russian, or Kazakh. Choose the report language when you add your recording. Recognition quality varies with language, accents, audio quality, and the installed model.",
  ],
  [
    "Can I check and change the report?",
    "Yes. Follow a timestamp to its transcript passage and play the recording. Edit action items, owners, deadlines, and priorities, or rename speakers when speaker separation is available. Changes are saved as a new report revision. Source matching is a review aid, not a guarantee of accuracy.",
  ],
  [
    "What can I take out of Megan?",
    "Download the full report as JSON, action items as a CSV spreadsheet, or dated tasks as an ICS calendar file. Calendar exports include only tasks with resolved dates. You can also ask questions about a completed meeting when local meeting chat is enabled.",
  ],
  [
    "How long can a recording be?",
    "The default limits are 100 MB and 30 minutes. The workspace shows the limits configured on your device. Processing time depends on the recording and your hardware; dense conversations can exceed the model’s context limit. Your transcript is retained if report generation needs a retry.",
  ],
];

export function LandingPage() {
  const [openFaq, setOpenFaq] = useState<string | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [outcome, setOutcome] = useState(0);
  const [showQuote, setShowQuote] = useState(false);
  const selected = outcomes[outcome];
  return (
    <div className="landing-page">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <a href="#" aria-label="Megan home">
          <Brand />
        </a>
        <nav className={menuOpen ? "open" : ""} aria-label="Main navigation">
          <a href="#how-it-works" onClick={() => setMenuOpen(false)}>
            How it works
          </a>
          <a href="#your-outcomes" onClick={() => setMenuOpen(false)}>
            Features
          </a>
          <a href="#privacy" onClick={() => setMenuOpen(false)}>
            Privacy
          </a>
        </nav>
        <a href="#/workspace" className="header-cta">
          Open workspace <ArrowUpRight size={15} />
        </a>
        <button
          className="mobile-menu icon-button"
          aria-label={menuOpen ? "Close menu" : "Open menu"}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen(!menuOpen)}
        >
          {menuOpen ? <X /> : <Menu />}
        </button>
      </header>
      <main id="main">
        <section className="landing-hero site-container">
          <div className="hero-copy">
            <h1>
              Your meetings,
              <br />
              <em>summarized.</em>
            </h1>
            <p>
              Record or upload a meeting. Get a transcript, summary, and action
              items.
            </p>
            <div className="hero-actions">
              <a href="#/new/record" className="pill-button">
                Record a meeting <ArrowUpRight size={18} />
              </a>
              <a href="#/example" className="landing-text-link">
                <Play size={13} /> View sample report
              </a>
            </div>
          </div>
          <ReportPreview />
        </section>
        <div className="format-ribbon">
          <span>Report languages</span>
          <div>
            English <i /> Русский <i /> Қазақша
          </div>
        </div>
        <section className="workflow-section site-container" id="how-it-works">
          <div className="section-intro">
            <div>
              <h2>How it works</h2>
            </div>
          </div>
          <div className="workflow-steps">
            {[
              {
                icon: Mic,
                title: "Record or upload",
                text: "Use your microphone or upload an MP3, WAV, or M4A recording.",
                note: "01",
              },
              {
                icon: Sparkles,
                title: "Review the report",
                text: "Read the summary and action items. Follow sources to check the transcript.",
                note: "02",
              },
              {
                icon: ArrowUpRight,
                title: "Edit and export",
                text: "Update tasks, owners, and dates. Download JSON, CSV, or calendar tasks.",
                note: "03",
              },
            ].map((step) => (
              <article key={step.note}>
                <div className="step-top">
                  <span>{step.note}</span>
                  <step.icon size={24} strokeWidth={1.4} />
                </div>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </article>
            ))}
          </div>
        </section>
        <section className="outcomes-section" id="your-outcomes">
          <div className="site-container">
            <div className="section-intro">
              <div>
                <h2>Review your meeting</h2>
              </div>
              <a href="#/example" className="landing-text-link">
                Open sample report <ArrowUpRight size={17} />
              </a>
            </div>
            <div className="outcome-layout">
              <div className="outcome-copy">
                <div
                  className="outcome-tabs"
                  role="group"
                  aria-label="Explore meeting outcomes"
                >
                  {outcomes.map((item, i) => (
                    <button
                      key={item.label}
                      aria-pressed={outcome === i}
                      onClick={() => {
                        setOutcome(i);
                        setShowQuote(false);
                      }}
                    >
                      <item.icon size={16} />
                      {item.label}
                    </button>
                  ))}
                </div>
                <div key={outcome} className="panel-enter">
                  <h3>{selected.title}</h3>
                  <p>{selected.text}</p>
                </div>
              </div>
              <div className="evidence-demo" key={`demo-${outcome}`}>
                <span className="landing-eyebrow">{selected.tag}</span>
                <div className="evidence-decision">
                  <CheckCheck size={20} />
                  <p>{selected.detail}</p>
                </div>
                <button
                  className="source-button"
                  aria-expanded={showQuote}
                  aria-controls="outcome-quote"
                  onClick={() => setShowQuote(!showQuote)}
                >
                  <Play size={11} fill="currentColor" /> {selected.time}{" "}
                  <span>{showQuote ? "Hide source" : "Follow the source"}</span>
                  <ArrowDown size={13} />
                </button>
                <div
                  id="outcome-quote"
                  className={`evidence-quote ${showQuote ? "revealed" : ""}`}
                >
                  {showQuote ? (
                    <>
                      <span>
                        {selected.speaker} <span>· {selected.time}</span>
                      </span>
                      <blockquote>“{selected.quote}”</blockquote>
                    </>
                  ) : (
                    <>
                      <AudioLines size={21} />
                      <p>Select the timestamp to see the original words.</p>
                    </>
                  )}
                </div>
                <small>Illustrative example · no recorded audio</small>
              </div>
            </div>
          </div>
        </section>
        <section className="privacy-section" id="privacy">
          <div className="site-container privacy-layout">
            <div>
              <h2>
                Processed on
                <br />
                <em>your device.</em>
              </h2>
            </div>
            <div className="privacy-copy">
              <p>
                Audio, transcripts, reports, and AI processing stay on the
                machine running Megan. No cloud AI account is required.
              </p>
              <small>
                Internet is needed for initial setup and model downloads. Your
                saved recordings remain on this machine until removed.
              </small>
            </div>
          </div>
        </section>
        <section className="faq-section site-container" id="questions">
          <div>
            <h2>Questions & answers</h2>
          </div>
          <div className="faq-list">
            {faqs.map(([question, answer]) => (
              <details key={question} open={openFaq === question}>
                <summary
                  onClick={(event) => {
                    event.preventDefault();
                    setOpenFaq((previous) =>
                      previous === question ? null : question,
                    );
                  }}
                >
                  {question}
                  <ChevronDown size={17} />
                </summary>
                <p>{answer}</p>
              </details>
            ))}
          </div>
        </section>
        <section className="final-invitation site-container">
          <h2>Start a meeting</h2>
          <a href="#/new/record" className="pill-button">
            Record a meeting <ArrowUpRight size={18} />
          </a>
          <a href="#/new/upload" className="landing-text-link">
            Upload audio <ArrowRight size={14} />
          </a>
          <span className="invitation-spark" aria-hidden="true">
            ✳
          </span>
        </section>
      </main>
      <footer className="site-footer site-container">
        <div>
          <a href="#" aria-label="Megan home">
            <Brand />
          </a>
        </div>
        <nav aria-label="Footer navigation">
          <a href="#/workspace">Your workspace</a>
          <a href="#privacy">Your privacy</a>
          <a href="#questions">Questions & answers</a>
        </nav>
      </footer>
    </div>
  );
}
