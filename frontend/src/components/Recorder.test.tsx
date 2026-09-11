import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Recorder } from "./Recorder";
import { UploadView } from "./UploadView";
import type { Health } from "../types";
import { canLeaveCapture } from "../navigation";

const stopTrack = vi.fn();
const closeContext = vi.fn().mockResolvedValue(undefined);
const getUserMedia = vi.fn();
const confirm = vi.fn(() => false);
let captureNode: {
  port: {
    onmessage: ((event: MessageEvent) => void) | null;
    postMessage: ReturnType<typeof vi.fn>;
  };
  disconnect: ReturnType<typeof vi.fn>;
};
beforeEach(() => {
  vi.clearAllMocks();
  getUserMedia.mockResolvedValue({
    getTracks: () => [{ stop: stopTrack }],
    getAudioTracks: () => [{}],
  });
  vi.stubGlobal("confirm", confirm);
  vi.stubGlobal(
    "AudioContext",
    class {
      sampleRate = 16000;
      state = "running";
      audioWorklet = { addModule: vi.fn().mockResolvedValue(undefined) };
      createMediaStreamSource = () => ({ connect: vi.fn() });
      destination = {};
      resume = vi.fn().mockResolvedValue(undefined);
      close = closeContext;
    },
  );
  vi.stubGlobal(
    "AudioWorkletNode",
    class {
      port = { onmessage: null, postMessage: vi.fn() };
      connect = vi.fn();
      disconnect = vi.fn();
      constructor() {
        captureNode = this;
      }
    },
  );
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia },
  });
  URL.createObjectURL = vi.fn(() => "blob:recording-test");
  URL.revokeObjectURL = vi.fn();
});
afterEach(() => vi.unstubAllGlobals());
function setup() {
  const onFile = vi.fn();
  const onRecording = vi.fn();
  const view = render(
    <Recorder
      maxSeconds={1800}
      maxBytes={10000000}
      disabled={false}
      onFile={onFile}
      onRecording={onRecording}
      onDate={vi.fn()}
    />,
  );
  return { ...view, onFile, onRecording, user: userEvent.setup() };
}

test("records, pauses, resumes, releases the mic, and keeps a downloadable WAV", async () => {
  const { user, onFile, onRecording, unmount } = setup();
  await user.click(screen.getByRole("button", { name: "Start recording" }));
  expect(screen.getByText("RECORDING YOUR MICROPHONE")).toBeInTheDocument();
  expect(canLeaveCapture()).toBe(false);
  await user.click(screen.getByRole("button", { name: "Pause" }));
  expect(captureNode.port.postMessage).toHaveBeenLastCalledWith("pause");
  await user.click(screen.getByRole("button", { name: "Resume" }));
  expect(captureNode.port.postMessage).toHaveBeenLastCalledWith("resume");
  act(() =>
    captureNode.port.onmessage?.({
      data: { chunk: new ArrayBuffer(32000), peak: 0.4 },
    } as MessageEvent),
  );
  await user.click(screen.getByRole("button", { name: "Finish recording" }));
  expect(captureNode.port.postMessage).toHaveBeenLastCalledWith("stop");
  act(() =>
    captureNode.port.onmessage?.({ data: { done: true } } as MessageEvent),
  );
  expect(stopTrack).toHaveBeenCalledOnce();
  expect(closeContext).toHaveBeenCalledOnce();
  expect(onFile).toHaveBeenCalledWith(
    expect.objectContaining({ type: "audio/wav", size: 32044 }),
  );
  expect(
    screen.getByRole("link", { name: "Download recording" }),
  ).toHaveAttribute("href", "blob:recording-test");
  expect(onRecording).toHaveBeenLastCalledWith(false);
  unmount();
  expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:recording-test");
  expect(canLeaveCapture()).toBe(true);
});

test("a denied microphone explains recovery without creating a recording", async () => {
  getUserMedia.mockRejectedValueOnce(
    new DOMException("denied", "NotAllowedError"),
  );
  const { user, onFile } = setup();
  await user.click(screen.getByRole("button", { name: "Start recording" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Microphone access was not allowed",
  );
  expect(onFile).not.toHaveBeenCalled();
  expect(canLeaveCapture()).toBe(true);
});

test("cancelling while permission is pending stops a late microphone stream", async () => {
  let grant: (value: unknown) => void;
  getUserMedia.mockReturnValueOnce(
    new Promise((resolve) => {
      grant = resolve;
    }),
  );
  const { user, onFile } = setup();
  await user.click(screen.getByRole("button", { name: "Start recording" }));
  await user.click(screen.getByRole("button", { name: "Cancel" }));
  await act(async () => {
    grant!({ getTracks: () => [{ stop: stopTrack }] });
  });
  expect(stopTrack).toHaveBeenCalledOnce();
  expect(screen.getByRole("button", { name: "Start recording" })).toBeEnabled();
  expect(onFile).toHaveBeenCalledWith(null);
});

test("a finished recording is submitted through the same upload flow and survives reselecting its tab", async () => {
  const user = userEvent.setup();
  const onUpload = vi.fn();
  render(
    <UploadView
      initialMode="record"
      health={
        {
          ready: true,
          busy: false,
          max_upload_mb: 100,
          max_duration_sec: 1800,
        } as Health
      }
      submitting={false}
      onUpload={onUpload}
      onExample={vi.fn()}
    />,
  );
  await user.click(screen.getByRole("button", { name: "Start recording" }));
  act(() =>
    captureNode.port.onmessage?.({
      data: { chunk: new ArrayBuffer(32000), peak: 0.4 },
    } as MessageEvent),
  );
  await user.click(screen.getByRole("button", { name: "Finish recording" }));
  act(() =>
    captureNode.port.onmessage?.({ data: { done: true } } as MessageEvent),
  );
  await user.click(screen.getByRole("button", { name: "Record a meeting" }));
  await user.selectOptions(screen.getByLabelText("Report language"), "en");
  await user.click(
    screen.getByRole("button", { name: "Create meeting report" }),
  );
  expect(onUpload).toHaveBeenCalledWith(
    expect.objectContaining({ type: "audio/wav", size: 32044 }),
    expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
    "en",
  );
});
