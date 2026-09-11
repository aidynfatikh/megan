# Megan frontend: product direction and implementation

Updated 11 September 2026.

## What the repository already did

The existing application had a strong recording-to-report pipeline: FastAPI, local PostgreSQL, Whisper, optional Sortformer speaker separation, Qwen through Ollama, timestamped evidence, action editing with revision checks, speaker renaming, JSON/CSV/ICS exports, and grounded meeting chat. Its React interface opened directly into an upload form and kept meetings mostly in a sidebar. There was no separate landing page, main meeting library, or browser recorder.

The product goal is a **private, reviewable meeting workspace**: capture the conversation, understand its outcomes, check the original words, and leave with usable next steps. Local processing and source traceability are concrete differentiators. Model quality and target-machine performance remain separate from frontend quality.

## How the Granola reference was used

The supplied `granola .html` was read as a design analysis and reference, not as instructions authorizing unrelated actions. The live [Granola homepage](https://www.granola.ai/) was also inspected.

Retained principles:

- Editorial serif headlines with readable sans-serif controls.
- Warm paper surfaces, olive actions, restrained borders, and generous whitespace.
- An actual readable report as the central visual object.
- Original paper collage elements around the report, with simple line artwork.
- Motion that explains a state: source reveal, selected outcomes, menu state, and recording feedback.
- A clear rhythm of light content, an olive outcome section, and a dark privacy section.

Megan has its own wordmark, copy, colors, document specimen, layout, and locally bundled Instrument Serif / Inter fonts. Granola fonts, logos, photography, claims, customer logos, pricing, and security policies were not copied. The landing page’s invented product-sync example is labeled; the workspace sample comes from the existing `/api/example` endpoint.

## Implemented experience

| Surface           | Behavior                                                                                                                                                                                                                |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Landing page      | Responsive hero; clickable source quotation; decisions/next-steps/sources selector; workflow explanation; accurate privacy and input/export information; native FAQ accordions; working workspace/capture/sample links. |
| Meeting dashboard | API-backed meeting rows, title/filename search, status filters, newest/oldest order, real counts, empty/loading/error states, and a sample-report shortcut in the sidebar footer.                                       |
| Action items      | Tasks across completed meetings, searchable by task/owner/meeting, with links to the report where editing and source review occur. No invented task-completion state.                                                   |
| Capture           | Microphone or file upload; report language; optional uploaded-meeting date; recording date prefilled only for recordings made now.                                                                                      |
| Recorder          | Microphone permission/error handling, real input-level meter, audio-sample duration, pause/resume, finish, local playback, WAV download, discard, and size/duration auto-stop.                                          |
| Meeting review    | Existing report, transcript search, source-to-audio playback, editing, speaker naming, exports, progress/retry, and chat retained. Saved-meeting URLs can be reopened and browser Back works.                           |
| Accessibility     | Visible focus; skip links; native form labels; state announcements; mobile navigation with focus trapping, Escape and focus return; accessible edit dialog; reduced-motion rules.                                       |

Routes use URL fragments so the built app works with the existing FastAPI `/` and `/assets` routes without server rewrite rules:

```text
/                          Landing page
/#/workspace               Meeting dashboard
/#/new/record              Microphone capture
/#/new/upload              Audio-file upload
/#/actions                 Cross-meeting action list
/#/example                 Illustrative report
/#/meetings/<job-id>       Saved or processing meeting
```

The workspace and recorder ship in the initial app bundle so capture opens immediately. Saved meeting lists and reports use skeleton placeholders while their API requests are pending. No new hosted services or runtime CDN dependencies were added.

## Recording and recovery details

`AudioWorklet` captures mono PCM outside the rendering thread and transfers small signed-16-bit buffers. The WAV header uses the actual AudioContext sample rate. The worklet flushes its last partial buffer before finishing and enforces the smaller of the API's duration and upload-size limits. Its output is silent, avoiding microphone feedback. See the [AudioWorklet documentation](https://developer.mozilla.org/en-US/docs/Web/API/AudioWorkletNode) and [microphone permission documentation](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia).

Microphone tracks and audio contexts are released on stop, cancellation, error, and unmount. A late permission response after cancellation is stopped immediately. Preview object URLs are revoked. Completed captures remain available if upload/processing cannot start. Internal navigation and tab closing warn when a microphone recording is unsaved.

Limits are explicit:

- Capture requires localhost/HTTPS and browser support for AudioWorklet.
- Microphone audio does not include a remote meeting app's internal audio. The UI directs remote-call users to upload their meeting tool's recording.
- Unsaved recordings live in browser memory. There is no crash recovery or background desktop recording service.
- Date resolution is based on the user-confirmed date, not file modification time.
- Local services must be ready to create a report. Recording/download and file selection remain available while services are unavailable.
- The existing single-request model scheduler still applies.
- Speaker and transcript accuracy require review. No confidence or completion percentages are invented.

## Backend issue found during verification

A controlled recording exposed a Whisper terminal hallucination whose timestamp extended to approximately 60 seconds in a 33-second file. The existing duration guard correctly rejected it. However, ASR segments had been assigned to the job before that guard, allowing a retry to skip transcription and reuse invalid sources.

The small change in `backend/worker.py` assigns segments only after duration validation and retranscribes invalid segments retained by older failed jobs. It keeps the existing strict guard. It does **not** pretend to fix Whisper hallucinations or silently clamp major errors. Two focused regression cases cover new and previously saved invalid ASR output. Restart an already-running API process to load this Python change.

## Verification

Automated checks:

- Production TypeScript/Vite build.
- 22 frontend tests, including actual WAV bytes, worklet clipping/channel mixing, pause/resume, partial-buffer flush, capture limits, microphone denial and cancellation, resource cleanup, active-tab preservation, recording-to-upload handoff, dashboard filtering, sample source navigation, late-response protection, and chat submission with a busy service.
- Eight focused backend/audio tests, including invalid-transcript retry regression cases.
- Ruff checks and formatting for the changed Python files.

Browser checks use the real local API and PostgreSQL on port 8765, with Vite on 5174 and the built frontend also served by the API. UI checks include desktop, 768px tablet, 390px mobile, and 1920px landing layouts, actual history, filters, source selection, transcript highlighting, mobile navigation/Escape/focus return, and console errors. The main views did not produce horizontal page overflow. Scoped computed-color checks informed the contrast adjustments; these are not a claim of a complete accessibility audit.

Browser microphone testing uses controlled synthetic speech, never a private meeting. A silent browser device also exercised the honest “No usable speech” result. The recorder produced a downloadable 16kHz mono PCM WAV, and the speech capture reached the real transcription pipeline.

A separate clean synthetic meeting (`4c46809d-ac5b-4b6c-82fa-742500ad40ad`) completed the real upload → transcription → diarization → report workflow in 43.9 seconds. Its six segments produced a decision, two actions, and an open question. Browser edits to task text, priority, and a confirmed due date persisted in report revision 3; JSON, CSV, and ICS export responses contained those edits. The calendar export included the resolved date and omitted the unresolved date. Clicking a source started the real audio at its 5.52-second timestamp. The browser automation's date-fill command did not set the native input, so date verification used native DOM input/change events before saving through the editor.

The local model scheduler was occupied by another request during final Q&A verification. The real busy state was checked in the browser; request submission and answer rendering were checked with the frontend API fixture. A new live model answer is not claimed as verified. Raw audio, test artifacts, and screenshots are kept under ignored `.local/`, not in Git. The three controlled verification meetings remain identifiable in local history.

This verification does not replace physical-microphone, Safari/iOS, long-recording, or RTX acceptance testing.

## Spacing and responsive refinement

The landing hero now uses 32–56px top padding instead of 123–150px on desktop, a smaller fluid headline, and adjacent primary/sample actions where space allows. Section spacing and the dashboard introduction were tightened so useful content appears sooner. Narrow phones keep the header controls inside the navigation; tablets keep the sample report unobstructed; phone previews size themselves to their content.

The landing, dashboard, upload, and sample-report pages were checked at 320, 390, 768, 1024, 1440, and 1920px widths (24 combinations). All loaded without page-level horizontal overflow or a development error overlay. The landing's primary action was visible without scrolling at each tested viewport. Production build and CSS formatting checks passed. Screenshots and measurement results are under ignored `.local/`.

## Interface copy

Screen text should identify the page, describe an action, show a result, or explain a relevant constraint. Decorative taglines and repeated privacy slogans were removed from the hero, preview, sidebar, recording flow, report, and footer. The landing now says “Your meetings, summarized.” and offers “Record a meeting” and “View sample report.” Its privacy explanation stays in the privacy section and FAQ.

The dashboard opens directly to meeting controls, filters, and history. Its promotional illustration, introductory slogans, duplicate statistics, and placeholder profile were removed. The capture page uses one form, with file limits, microphone guidance, and date/language controls next to the actions they explain. Sample labels, errors, processing states, and source-review information remain explicit. The same 24 responsive combinations were checked again after the copy changes.

## Processing status

The top-right Local processing control now reflects `/api/health`: green when services are ready, red when something needs attention, and neutral during the first check. Clicking it opens a small popover with relevant problems in plain language and a Check again button. Health refreshes independently of meeting history every 10 seconds; failed requests clear the previous ready state. Normal processing is not an error. Optional speaker separation problems explain whether reports can still be created.

The separate System status navigation item and technical setup panel were removed. The popover supports Escape, outside-click and keyboard dismissal, and fits a 320px screen. Verification: 26 frontend tests and the production build passed; desktop/mobile browser checks covered the disconnected state and a simulated healthy response.

## Immediate capture and loading placeholders

“Record a meeting” opens the capture form directly, without a workspace loading screen or entry fade. Health and history requests do not block the recorder. Recent meetings, the meeting library, action lists, and saved reports use placeholders shaped like their eventual content, with accessible loading labels and reduced-motion support. Pending history no longer flashes an empty-library message or zero counts.

Verification: 29 frontend tests and the production build passed. Browser checks held API responses pending and confirmed that the recorder stayed available with no intervening loading screen. Library and report placeholders fit a 320px viewport without horizontal overflow.

## FAQ and workspace layout

The FAQ heading is vertically centered beside the question list. Opening an answer closes the previous answer, and the same question can be toggled closed. The new-meeting form now fills the same content area as the dashboard, including tablet widths. The workspace header stays sticky on mobile.

The desktop sidebar collapses to a 72px rail with the Megan mark and navigation icons. Following the Kalqan sidebar interaction, hovering or focusing the mark reveals the expand icon. Navigation retains accessible labels and tooltips; the preference survives navigation and reloads. Mobile continues to use a full drawer, independent of the desktop preference, and switching to desktop clears its scroll lock. The inline How it works panel and its sidebar entry were removed.

Verification: 33 frontend tests, formatting, and production build passed. Browser checks confirmed the icon/mark hover, full-width capture form, sticky mobile header, and mobile drawer behavior after desktop collapse.

Sidebar collapse keeps the logo, icon column, padding, and button heights fixed while the panel changes width. Focus moves between the toggles without scrolling the clipped header. Browser animation checks at 1440px and 900px measured no horizontal or vertical movement of the mark or navigation icons in either direction; the mobile drawer still fits at 390px. All 33 frontend tests and the production build passed after the adjustment.

The sample-report shortcut now sits in the sidebar footer on every workspace page, replacing the empty-library banner. It becomes a labeled report icon in the collapsed rail, stays anchored during collapse, and appears with its full label in the mobile drawer. It uses the existing sample-report route and closes the mobile drawer on selection.
