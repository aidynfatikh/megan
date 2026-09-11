// Capture mono PCM off the UI thread. Outputs remain silent to prevent feedback.
class MeganRecorder extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.buffer = new Int16Array(4096);
    this.offset = 0;
    this.total = 0;
    this.limit = options.processorOptions.maxSamples;
    this.paused = false;
    this.stopped = false;
    this.port.onmessage = ({ data }) => {
      if (data === "pause") {
        this.flush();
        this.paused = true;
      }
      if (data === "resume") this.paused = false;
      if (data === "stop") {
        this.stopped = true;
        this.flush();
        this.port.postMessage({ done: true });
      }
    };
  }
  flush() {
    if (!this.offset) return;
    const chunk = this.buffer.slice(0, this.offset);
    let peak = 0;
    for (const value of chunk) peak = Math.max(peak, Math.abs(value) / 32768);
    this.port.postMessage({ chunk: chunk.buffer, peak }, [chunk.buffer]);
    this.offset = 0;
  }
  process(inputs) {
    if (this.stopped) return false;
    const channels = inputs[0];
    if (this.paused || !channels?.length) return true;
    for (let i = 0; i < channels[0].length; i++) {
      let sample = 0;
      for (const channel of channels) sample += channel[i] / channels.length;
      sample = Math.max(-1, Math.min(1, sample));
      this.buffer[this.offset++] = Math.round(
        sample * (sample < 0 ? 32768 : 32767),
      );
      this.total++;
      if (this.offset === this.buffer.length) this.flush();
      if (this.total >= this.limit) {
        this.flush();
        this.stopped = true;
        this.port.postMessage({ done: true, limitReached: true });
        return false;
      }
    }
    return true;
  }
}
registerProcessor("megan-recorder", MeganRecorder);
