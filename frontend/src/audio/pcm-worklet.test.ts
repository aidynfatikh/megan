// @vitest-environment node
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { wavBlob } from "./wav";

type Message = {
  chunk?: ArrayBuffer;
  peak?: number;
  done?: boolean;
  limitReached?: boolean;
};
type Processor = {
  port: { onmessage: (event: { data: string }) => void };
  process: (input: Float32Array[][]) => boolean;
};
function recorder(maxSamples = 16000) {
  const messages: Message[] = [];
  let Recording: new (options: unknown) => Processor;
  runInNewContext(
    readFileSync(new URL("./pcm-worklet.js", import.meta.url), "utf8"),
    {
      AudioWorkletProcessor: class {
        port = { postMessage: (message: Message) => messages.push(message) };
      },
      registerProcessor: (_name: string, constructor: typeof Recording) => {
        Recording = constructor;
      },
      Int16Array,
      Math,
    },
  );
  return {
    instance: new Recording!({ processorOptions: { maxSamples } }),
    messages,
  };
}

test("recording clips loud input, mixes channels, and flushes its last partial chunk", () => {
  const { instance, messages } = recorder();
  instance.process([[new Float32Array([-2, -1, 0, 1, 2])]]);
  instance.port.onmessage({ data: "stop" });
  expect(Array.from(new Int16Array(messages[0].chunk!))).toEqual([
    -32768, -32768, 0, 32767, 32767,
  ]);
  expect(messages.at(-1)).toEqual({ done: true });
  expect(instance.process([])).toBe(false);
});

test("pauses omit audio, resume captures again, and size limits stop before overflow", () => {
  const { instance, messages } = recorder(3);
  instance.process([[new Float32Array([1]), new Float32Array([-1])]]);
  instance.port.onmessage({ data: "pause" });
  instance.process([[new Float32Array([1, 1, 1])]]);
  instance.port.onmessage({ data: "resume" });
  instance.process([[new Float32Array([0.5, -0.5, 1, 1])]]);
  const data = messages.flatMap((message) =>
    message.chunk ? Array.from(new Int16Array(message.chunk)) : [],
  );
  expect(data).toEqual([0, 16384, -16384]);
  expect(messages.at(-1)).toEqual({ done: true, limitReached: true });
});

test("WAV output declares the actual sample rate, duration, PCM encoding, and payload size", async () => {
  const chunk = new Int16Array([0, 32767, -32768]);
  const blob = wavBlob([chunk.buffer], 16000);
  const bytes = await blob.arrayBuffer();
  const view = new DataView(bytes);
  const ascii = (from: number, to: number) =>
    new TextDecoder().decode(bytes.slice(from, to));
  expect(ascii(0, 4)).toBe("RIFF");
  expect(ascii(8, 12)).toBe("WAVE");
  expect(ascii(36, 40)).toBe("data");
  expect(view.getUint32(4, true)).toBe(bytes.byteLength - 8);
  expect(view.getUint16(20, true)).toBe(1);
  expect(view.getUint16(22, true)).toBe(1);
  expect(view.getUint32(24, true)).toBe(16000);
  expect(view.getUint32(28, true)).toBe(32000);
  expect(view.getUint16(34, true)).toBe(16);
  expect(view.getUint32(40, true)).toBe(6);
  expect(Array.from(new Int16Array(bytes.slice(44)))).toEqual([
    0, 32767, -32768,
  ]);
});
