import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { api } from "./api";
import type { Health, Job } from "./types";
import rawExample from "./test/example.json";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  api: {
    health: vi.fn(),
    jobs: vi.fn(),
    job: vi.fn(),
    example: vi.fn(),
    chat: vi.fn(),
    notionStatus: vi.fn(),
  },
}));
const healthy: Health = {
  ready: true,
  database: true,
  asr: true,
  ollama: true,
  ffmpeg: true,
  busy: false,
  local_only: true,
  asr_backend: "whisper_cpp",
  asr_model: "whisper",
  llm: "qwen",
  diarization: "none",
  diarization_ready: false,
  chat_enabled: true,
  max_upload_mb: 60,
  max_duration_sec: 600,
};
const sample = rawExample as Job;
const ready = {
  ...sample,
  id: "ready-meeting",
  filename: "product-sync.wav",
  provenance: { ...sample.provenance, sample: false },
};
const failed = {
  ...ready,
  id: "failed-meeting",
  filename: "planning.wav",
  report: null,
  status: "failed" as const,
};
beforeEach(() => {
  localStorage.removeItem("megan.sidebar.collapsed");
  vi.mocked(api.health).mockResolvedValue(healthy);
  vi.mocked(api.jobs).mockResolvedValue([ready, failed]);
  vi.mocked(api.job).mockResolvedValue(ready);
  vi.mocked(api.example).mockResolvedValue(sample);
  vi.mocked(api.notionStatus).mockResolvedValue({
    configured: false,
    destination: null,
  });
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  window.scrollTo = vi.fn();
  window.matchMedia = vi.fn().mockReturnValue({ matches: false });
  Element.prototype.scrollIntoView = vi.fn();
});
function start(hash = "") {
  window.history.replaceState(null, "", `/ ${hash}`.replace("/ ", "/"));
  render(<App />);
  return userEvent.setup();
}

test("landing source interaction explains evidence and opens the real workspace", async () => {
  const user = start();
  expect(
    screen.getByRole("heading", {
      name: "Your meetings, summarized.",
    }),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "12:42 View source" }));
  expect(
    screen.getByText("Illustrative transcript · no audio"),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("link", { name: "Open workspace" }));
  expect(
    await screen.findByRole("heading", { name: "Meetings" }),
  ).toBeInTheDocument();
  expect(
    await screen.findByRole("link", { name: /planning.wav/ }),
  ).toBeInTheDocument();
});

test("meeting filters, searches, and cross-meeting actions use actual API data", async () => {
  const user = start("#/workspace");
  const library = await screen.findByRole("region", {
    name: "Your meetings 2",
  });
  await user.click(
    within(library).getByRole("button", { name: "Needs attention" }),
  );
  expect(
    within(library).getByRole("link", { name: /planning.wav/ }),
  ).toBeInTheDocument();
  expect(
    within(library).queryByRole("link", { name: /Website launch sync/ }),
  ).not.toBeInTheDocument();
  await user.type(
    screen.getByRole("textbox", { name: "Search meetings" }),
    "no-such-meeting",
  );
  expect(screen.getByText("No matches found.")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Clear filters" }));
  await user.click(screen.getByRole("button", { name: /Action items/ }));
  expect(
    await screen.findByRole("heading", { name: "Action items" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(sample.report!.action_items[0].task),
  ).toBeInTheDocument();
});

test("sample deep links reopen, and a source leads into its transcript", async () => {
  const user = start("#/example");
  expect(await screen.findByText("Example report")).toBeInTheDocument();
  const buttons = screen.getAllByRole("button", { name: /View source S2/ });
  await user.click(buttons[0]);
  await user.click(screen.getByRole("button", { name: "See in transcript" }));
  expect(
    screen.getByRole("textbox", { name: "Search transcript" }),
  ).toBeInTheDocument();
  expect(document.querySelector(".transcript-line.active")).not.toBeNull();
  await user.click(screen.getByRole("link", { name: "Skip to content" }));
  expect(window.location.hash).toBe("#/example");
});

test("a late meeting response cannot replace the dashboard after navigation", async () => {
  let resolve: (job: Job) => void;
  vi.mocked(api.job).mockReturnValueOnce(
    new Promise((done) => {
      resolve = done;
    }),
  );
  const user = start("#/meetings/slow");
  await screen.findByRole("status", { name: "Loading meeting" });
  await user.click(screen.getByRole("button", { name: /All meetings/ }));
  await screen.findByRole("heading", { name: "Meetings" });
  await act(async () => {
    resolve!(ready);
  });
  expect(screen.getByRole("heading", { name: "Meetings" })).toBeInTheDocument();
});

test("meeting chat explains a busy service and submits once it is available", async () => {
  vi.mocked(api.health).mockResolvedValue({
    ...healthy,
    busy: true,
  } as Health);
  const user = start("#/meetings/ready-meeting");
  const input = await screen.findByRole("textbox", {
    name: "Question about this meeting",
  });
  await user.type(input, "Who is preparing the checklist?");
  expect(screen.getByText(/Megan is processing another request/)).toBeVisible();
  expect(screen.getByRole("button", { name: "Ask meeting" })).toBeDisabled();
  await user.keyboard("{Enter}");
  expect(api.chat).not.toHaveBeenCalled();

  vi.mocked(api.health).mockResolvedValue({
    ...healthy,
    busy: false,
  } as Health);
  vi.mocked(api.chat).mockResolvedValue({
    answer: "Maya will prepare the checklist.",
    supported: true,
    citations: [
      {
        segment_id: sample.segments[0].id,
        quote: sample.segments[0].text,
        start: sample.segments[0].start,
        end: sample.segments[0].end,
      },
    ],
  });
  // Reopen the workspace to refresh service health without relying on a timer.
  await user.click(screen.getByRole("link", { name: "Megan home" }));
  await user.click(screen.getByRole("link", { name: "Open workspace" }));
  await user.click(
    await screen.findByRole("link", { name: /Website launch sync/ }),
  );
  await user.type(
    await screen.findByRole("textbox", { name: "Question about this meeting" }),
    "Who is preparing the checklist?",
  );
  await user.click(screen.getByRole("button", { name: "Ask meeting" }));
  expect(
    await screen.findByText("Maya will prepare the checklist."),
  ).toBeVisible();
  expect(api.chat).toHaveBeenCalledWith(
    "ready-meeting",
    "Who is preparing the checklist?",
  );
});

test("processing status stays green while busy and supports keyboard dismissal", async () => {
  vi.mocked(api.health).mockResolvedValue({ ...healthy, busy: true });
  const user = start("#/workspace");
  const status = await screen.findByRole("button", {
    name: "Local processing: Ready",
  });
  expect(status).toHaveClass("is-ready");
  expect(
    screen.queryByRole("button", { name: "System status" }),
  ).not.toBeInTheDocument();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  await user.click(status);
  const popup = screen.getByRole("dialog", { name: "Everything is ready" });
  expect(popup).toHaveFocus();
  expect(
    within(popup).getByText(/Megan is working on another request/),
  ).toBeVisible();
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(status).toHaveFocus();
  await user.keyboard("{Enter}");
  expect(screen.getByRole("dialog")).toBeVisible();
  await user.click(screen.getByRole("heading", { name: "Meetings" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("missing services show a red indicator with only relevant plain-language problems", async () => {
  vi.mocked(api.health).mockResolvedValue({
    ...healthy,
    ready: false,
    asr: false,
    ollama: false,
  });
  const user = start("#/workspace");
  const status = await screen.findByRole("button", {
    name: "Local processing: Needs attention",
  });
  expect(status).toHaveClass("is-error");
  await user.click(status);
  const popup = screen.getByRole("dialog");
  expect(
    within(popup).getByText(/Speech recognition isn’t ready/),
  ).toBeVisible();
  expect(
    within(popup).getByText(/The report generator isn’t ready/),
  ).toBeVisible();
  expect(within(popup).queryByText(/Meeting storage/)).not.toBeInTheDocument();
  expect(within(popup).queryByText(/Speaker labels/)).not.toBeInTheDocument();
});

test("a lost connection clears a previously green status and check again recovers it", async () => {
  const user = start("#/workspace");
  await user.click(
    await screen.findByRole("button", { name: "Local processing: Ready" }),
  );
  vi.mocked(api.health).mockRejectedValueOnce(new Error("Failed to fetch"));
  await user.click(screen.getByRole("button", { name: "Check again" }));
  expect(
    await screen.findByRole("button", {
      name: "Local processing: Needs attention",
    }),
  ).toHaveClass("is-error");
  expect(
    screen.getByText(/Megan isn’t running or can’t be reached/),
  ).toBeVisible();
  expect(screen.queryByText("Failed to fetch")).not.toBeInTheDocument();
  await user.click(await screen.findByRole("button", { name: "Check again" }));
  expect(
    await screen.findByRole("button", { name: "Local processing: Ready" }),
  ).toHaveClass("is-ready");
  expect(
    screen.getByRole("dialog", { name: "Everything is ready" }),
  ).toBeVisible();
});

test("status remains neutral until the first check and explains unavailable optional speaker labels", async () => {
  let resolve: (health: Health) => void;
  vi.mocked(api.health).mockReturnValueOnce(
    new Promise((done) => {
      resolve = done;
    }),
  );
  const user = start("#/workspace");
  const status = await screen.findByRole("button", {
    name: "Local processing: Checking",
  });
  expect(status).toHaveClass("is-checking");
  await user.click(status);
  expect(screen.getByRole("button", { name: "Checking…" })).toBeDisabled();
  await act(async () => {
    resolve!({ ...healthy, diarization: "sortformer_nemo" });
  });
  expect(
    screen.getByRole("button", { name: "Local processing: Needs attention" }),
  ).toHaveClass("is-error");
  expect(screen.getByText(/You can still create reports/)).toBeVisible();
});

test("the landing recorder opens immediately while health and history are still pending", async () => {
  vi.mocked(api.health).mockReturnValueOnce(new Promise(() => {}));
  vi.mocked(api.jobs).mockReturnValueOnce(new Promise(() => {}));
  const user = start();
  await user.click(
    within(screen.getByRole("main")).getAllByRole("link", {
      name: "Record a meeting",
    })[0],
  );
  expect(screen.getByRole("heading", { name: "New meeting" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Start recording" })).toBeEnabled();
  expect(screen.queryByText(/Opening your workspace/)).not.toBeInTheDocument();
  expect(screen.queryByText("No meetings yet.")).not.toBeInTheDocument();
  expect(
    screen.getByRole("status", { name: "Loading recent meetings" }),
  ).toHaveAttribute("aria-busy", "true");
});

test("meeting rows use placeholders until real data arrives", async () => {
  let resolve: (jobs: Job[]) => void;
  vi.mocked(api.jobs).mockReturnValueOnce(
    new Promise((done) => {
      resolve = done;
    }),
  );
  start("#/workspace");
  expect(
    screen.getByRole("status", { name: "Loading meetings" }),
  ).toBeInTheDocument();
  expect(screen.queryByText("No meetings yet.")).not.toBeInTheDocument();
  await act(async () => {
    resolve!([ready]);
  });
  expect(
    screen.queryByRole("status", { name: "Loading meetings" }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: /Website launch sync/ }),
  ).toBeVisible();
});

test("a report skeleton gives way to the loaded report", async () => {
  let resolve: (job: Job) => void;
  vi.mocked(api.job).mockReturnValueOnce(
    new Promise((done) => {
      resolve = done;
    }),
  );
  start("#/meetings/ready-meeting");
  expect(
    screen.getByRole("status", { name: "Loading meeting" }),
  ).toHaveAttribute("aria-busy", "true");
  await act(async () => {
    resolve!(ready);
  });
  expect(
    screen.queryByRole("status", { name: "Loading meeting" }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Website launch sync" }),
  ).toBeVisible();
});

test("the FAQ opens one answer at a time and lets the open answer close", async () => {
  const user = start();
  const first = screen.getByText("How do I bring a meeting into Megan?");
  const second = screen.getByText("Does my audio leave this device?");
  await user.click(first);
  expect(first.closest("details")).toHaveAttribute("open");
  await user.click(second);
  expect(first.closest("details")).not.toHaveAttribute("open");
  expect(second.closest("details")).toHaveAttribute("open");
  expect(document.querySelectorAll(".faq-list details[open]")).toHaveLength(1);
  await user.click(second);
  expect(document.querySelectorAll(".faq-list details[open]")).toHaveLength(0);
});

test("sidebar collapse preserves the selected recording and works with icon navigation", async () => {
  const user = start("#/new/upload");
  await user.upload(
    screen.getByLabelText("Meeting recording"),
    new File(["audio"], "team.wav", { type: "audio/wav" }),
  );
  await user.click(screen.getByRole("button", { name: "Collapse sidebar" }));
  expect(document.querySelector(".app-shell")).toHaveClass("sidebar-collapsed");
  expect(localStorage.getItem("megan.sidebar.collapsed")).toBe("1");
  expect(screen.getByText("team.wav")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "Expand sidebar" }));
  expect(document.querySelector(".app-shell")).not.toHaveClass(
    "sidebar-collapsed",
  );
  expect(screen.getByText("team.wav")).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "How it works" }),
  ).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Collapse sidebar" }));
  const sidebar = screen.getByRole("complementary", {
    name: "Workspace navigation",
  });
  await user.click(
    within(sidebar).getByRole("button", { name: "Action items" }),
  );
  expect(
    await screen.findByRole("heading", { name: "Action items" }),
  ).toBeVisible();
  expect(document.querySelector(".app-shell")).toHaveClass("sidebar-collapsed");
});

test("the collapsed sidebar preference survives reopening the workspace", async () => {
  localStorage.setItem("megan.sidebar.collapsed", "1");
  const user = start("#/workspace");
  expect(document.querySelector(".app-shell")).toHaveClass("sidebar-collapsed");
  await user.click(screen.getByRole("link", { name: "Megan home" }));
  await user.click(screen.getByRole("link", { name: "Open workspace" }));
  expect(document.querySelector(".app-shell")).toHaveClass("sidebar-collapsed");
});

test("the mobile drawer still closes with Escape when the desktop rail is collapsed", async () => {
  localStorage.setItem("megan.sidebar.collapsed", "1");
  const user = start("#/workspace");
  const trigger = screen.getByRole("button", { name: "Open navigation" });
  await user.click(trigger);
  expect(
    screen.getByRole("dialog", { name: "Workspace navigation" }),
  ).toBeVisible();
  expect(document.querySelector(".main-shell")).toHaveAttribute("inert");
  await user.keyboard("{Escape}");
  expect(
    screen.queryByRole("dialog", { name: "Workspace navigation" }),
  ).not.toBeInTheDocument();
  expect(document.querySelector(".main-shell")).not.toHaveAttribute("inert");
  expect(trigger).toHaveFocus();
});

test("citations require explicit playback and closing stops audio without scrolling", async () => {
  const user = start("#/meetings/ready-meeting");
  const sources = await screen.findAllByRole("button", {
    name: /View source S2/,
  });
  await user.click(sources[0]);
  expect(HTMLMediaElement.prototype.play).not.toHaveBeenCalled();
  expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Play passage" }));
  expect(HTMLMediaElement.prototype.play).toHaveBeenCalledOnce();
  const pause = vi.mocked(HTMLMediaElement.prototype.pause);
  pause.mockClear();
  await user.click(screen.getByRole("button", { name: "Close source" }));
  expect(pause).toHaveBeenCalledOnce();
  expect(
    screen.queryByRole("complementary", { name: "Selected source" }),
  ).not.toBeInTheDocument();
});
