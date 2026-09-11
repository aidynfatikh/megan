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
  },
}));
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
  vi.mocked(api.health).mockResolvedValue({
    ready: true,
    busy: false,
  } as Health);
  vi.mocked(api.jobs).mockResolvedValue([ready, failed]);
  vi.mocked(api.job).mockResolvedValue(ready);
  vi.mocked(api.example).mockResolvedValue(sample);
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
  await act(async () => {
    await vi.dynamicImportSettled();
  });
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
  await screen.findByText("Opening your meeting…");
  await user.click(screen.getByRole("button", { name: /All meetings/ }));
  await screen.findByRole("heading", { name: "Meetings" });
  await act(async () => {
    resolve!(ready);
  });
  expect(screen.getByRole("heading", { name: "Meetings" })).toBeInTheDocument();
});

test("meeting chat explains a busy service and submits once it is available", async () => {
  vi.mocked(api.health).mockResolvedValue({
    ready: true,
    busy: true,
    chat_enabled: true,
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
    ready: true,
    busy: false,
    chat_enabled: true,
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
