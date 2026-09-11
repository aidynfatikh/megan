import { useEffect, useRef, useState } from "react";
import {
  ArrowDownToLine,
  Check,
  LoaderCircle,
  Mic,
  Pause,
  Play,
  Square,
  Trash2,
} from "lucide-react";
import workletUrl from "../audio/pcm-worklet.js?url";
import { wavBlob } from "../audio/wav";
import { timestamp } from "../api";
import { protectCapture } from "../navigation";

type State = "idle" | "requesting" | "recording" | "paused" | "ready";
export function Recorder({
  maxSeconds,
  maxBytes,
  disabled,
  onRecording,
  onFile,
  onDate,
}: {
  maxSeconds: number;
  maxBytes: number;
  disabled: boolean;
  onRecording: (active: boolean) => void;
  onFile: (file: File | null) => void;
  onDate: (date: string) => void;
}) {
  const [state, setState] = useState<State>("idle");
  const [seconds, setSeconds] = useState(0);
  const [level, setLevel] = useState(0);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState("");
  const [filename, setFilename] = useState("");
  const [limitReached, setLimitReached] = useState(false);
  const context = useRef<AudioContext | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const node = useRef<AudioWorkletNode | null>(null);
  const chunks = useRef<ArrayBuffer[]>([]);
  const size = useRef(0);
  const generation = useRef(0);
  const finalizing = useRef(false);
  const callbacks = useRef({ onRecording, onFile, onDate });
  callbacks.current = { onRecording, onFile, onDate };

  function release() {
    stream.current?.getTracks().forEach((track) => track.stop());
    node.current?.disconnect();
    if (context.current && context.current.state !== "closed")
      void context.current.close();
    stream.current = null;
    node.current = null;
    context.current = null;
  }
  useEffect(
    () => () => {
      generation.current++;
      release();
      protectCapture(false);
      callbacks.current.onRecording(false);
    },
    [],
  );
  useEffect(() => {
    if (!preview) return;
    return () => URL.revokeObjectURL(preview);
  }, [preview]);
  useEffect(() => {
    if (state === "idle") return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [state]);

  function finish(rate: number, reachedLimit = false) {
    if (finalizing.current) return;
    finalizing.current = true;
    release();
    callbacks.current.onRecording(false);
    setLevel(0);
    if (!size.current) {
      setError("No audio was captured. Check your microphone and try again.");
      setState("idle");
      protectCapture(false);
      return;
    }
    const blob = wavBlob(chunks.current, rate);
    const name = `Meeting-${new Date().toISOString().replace(/[:.]/g, "-")}.wav`;
    const file = new File([blob], name, { type: "audio/wav" });
    setFilename(name);
    setPreview(URL.createObjectURL(file));
    setSeconds(size.current / (rate * 2));
    setLimitReached(reachedLimit);
    setState("ready");
    chunks.current = [];
    callbacks.current.onFile(file);
  }

  async function start() {
    if (!navigator.mediaDevices?.getUserMedia || !window.AudioContext) {
      setError(
        "Microphone recording needs a supported browser on localhost or HTTPS. You can upload an audio file instead.",
      );
      return;
    }
    const attempt = ++generation.current;
    setState("requesting");
    setError("");
    setSeconds(0);
    setLimitReached(false);
    finalizing.current = false;
    chunks.current = [];
    size.current = 0;
    protectCapture(true);
    callbacks.current.onRecording(true);
    try {
      const mic = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
        video: false,
      });
      if (generation.current !== attempt) {
        mic.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = mic;
      const ctx = new AudioContext({ sampleRate: 16000 });
      context.current = ctx;
      await ctx.audioWorklet.addModule(workletUrl);
      if (generation.current !== attempt) return;
      const recorder = new AudioWorkletNode(ctx, "megan-recorder", {
        processorOptions: {
          maxSamples: Math.max(
            1,
            Math.floor(
              Math.min(maxSeconds * ctx.sampleRate, (maxBytes - 44) / 2),
            ),
          ),
        },
      });
      node.current = recorder;
      const source = ctx.createMediaStreamSource(mic);
      source.connect(recorder);
      recorder.connect(ctx.destination);
      recorder.port.onmessage = ({
        data,
      }: MessageEvent<{
        chunk?: ArrayBuffer;
        peak?: number;
        done?: boolean;
        limitReached?: boolean;
      }>) => {
        if (generation.current !== attempt || finalizing.current) return;
        if (data.chunk) {
          chunks.current.push(data.chunk);
          size.current += data.chunk.byteLength;
          setSeconds(size.current / (ctx.sampleRate * 2));
          setLevel(data.peak ?? 0);
        }
        if (data.done) finish(ctx.sampleRate, data.limitReached);
      };
      recorder.onprocessorerror = () => {
        setError(
          "Audio capture stopped unexpectedly. Any captured audio is available below.",
        );
        finish(ctx.sampleRate);
      };
      mic.getAudioTracks()[0].onended = () => {
        setError(
          "The microphone disconnected. Any captured audio is available below.",
        );
        recorder.port.postMessage("stop");
      };
      await ctx.resume();
      if (generation.current !== attempt) return;
      const now = new Date();
      callbacks.current.onDate(
        `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`,
      );
      setState("recording");
    } catch (err) {
      if (generation.current !== attempt) return;
      release();
      setState("idle");
      callbacks.current.onRecording(false);
      protectCapture(false);
      const name = err instanceof DOMException ? err.name : "";
      setError(
        name === "NotAllowedError"
          ? "Microphone access was not allowed. Enable it in your browser’s site settings, then try again or upload a recording."
          : name === "NotFoundError"
            ? "No microphone was found. Connect one or upload an audio file."
            : "Couldn’t start the microphone. Check that it is available, then try again or upload a recording.",
      );
    }
  }

  function discard() {
    if (
      state === "ready" &&
      !window.confirm(
        "Discard this recording? Download a copy first if you want to keep it.",
      )
    )
      return;
    generation.current++;
    release();
    chunks.current = [];
    size.current = 0;
    setState("idle");
    setPreview("");
    setSeconds(0);
    setLevel(0);
    setError("");
    onFile(null);
    onRecording(false);
    protectCapture(false);
  }

  return (
    <div className={`recorder recorder-${state}`}>
      {state === "idle" || state === "requesting" ? (
        <>
          <span className="record-mic">
            <Mic size={29} strokeWidth={1.5} />
          </span>
          <h2>A little space to think out loud.</h2>
          <p>Record your microphone. Stay in the conversation.</p>
          <button
            type="button"
            className="primary-button record-start"
            onClick={() => void start()}
            disabled={disabled || state === "requesting"}
          >
            {state === "requesting" ? (
              <>
                <LoaderCircle size={17} className="spin" />
                Waiting for microphone…
              </>
            ) : (
              <>
                <Mic size={17} /> Start recording
              </>
            )}
          </button>
          {state === "requesting" && (
            <button type="button" className="text-button" onClick={discard}>
              Cancel
            </button>
          )}
          <span className="recording-limit">
            Up to {Math.floor(maxSeconds / 60)} minutes · microphone only
          </span>
        </>
      ) : state === "ready" ? (
        <>
          <span className="record-mic completed">
            <Check size={28} />
          </span>
          <h2>Your conversation, captured.</h2>
          <p>{timestamp(seconds)} of audio · ready to turn into a report</p>
          <audio controls src={preview} aria-label="Preview your recording" />
          <div className="recording-ready-actions">
            <a href={preview} download={filename} className="text-button">
              <ArrowDownToLine size={15} /> Download recording
            </a>
            <button
              type="button"
              className="text-button"
              onClick={discard}
              disabled={disabled}
            >
              <Trash2 size={14} /> Discard
            </button>
          </div>
          {limitReached && (
            <p className="field-hint" role="status">
              The recording limit was reached. Your audio is ready to save.
            </p>
          )}
        </>
      ) : (
        <>
          <div
            className={`recording-indicator ${state === "paused" ? "paused" : ""}`}
          >
            <i />
            {state === "paused" ? "PAUSED" : "RECORDING YOUR MICROPHONE"}
          </div>
          <div
            className="recording-timer"
            aria-label={`${state === "paused" ? "Paused at" : "Recorded"} ${timestamp(seconds)}`}
          >
            {timestamp(seconds)}
          </div>
          <div
            className="input-meter"
            role="meter"
            aria-label="Microphone input level"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(level * 100)}
          >
            {Array.from({ length: 32 }, (_, i) => (
              <i
                key={i}
                style={{
                  transform: `scaleY(${state === "paused" ? 0.09 : Math.max(0.09, Math.min(1, level * 6) * (0.35 + ((i * 7) % 11) / 16))})`,
                }}
              />
            ))}
          </div>
          <p>
            {state === "paused"
              ? "Take your time. Resume whenever you’re ready."
              : level < 0.006
                ? "Listening… speak near your microphone."
                : "You’re coming through. Stay in the moment."}
          </p>
          <div className="recording-controls">
            <button
              type="button"
              className="secondary-button"
              onClick={() => {
                node.current?.port.postMessage(
                  state === "paused" ? "resume" : "pause",
                );
                setState(state === "paused" ? "recording" : "paused");
                setLevel(0);
              }}
            >
              {state === "paused" ? (
                <>
                  <Play size={16} /> Resume
                </>
              ) : (
                <>
                  <Pause size={16} /> Pause
                </>
              )}
            </button>
            <button
              type="button"
              className="primary-button stop-recording"
              onClick={() => node.current?.port.postMessage("stop")}
            >
              <Square size={12} fill="currentColor" /> Finish recording
            </button>
          </div>
          <small>
            Keep this tab open. Your report is created after you finish.
          </small>
        </>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <p className="microphone-note">
        For in-person conversations, let everyone know you’re recording. Remote
        call? Upload your meeting tool’s recording to include all voices.
      </p>
    </div>
  );
}
