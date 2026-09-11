/** Mono, signed 16-bit little-endian PCM in a standard RIFF/WAVE container. */
export function wavBlob(chunks: ArrayBuffer[], sampleRate: number): Blob {
  const size = chunks.reduce((total, chunk) => total + chunk.byteLength, 0);
  const header = new ArrayBuffer(44);
  const view = new DataView(header);
  function text(at: number, value: string) {
    for (let i = 0; i < value.length; i++)
      view.setUint8(at + i, value.charCodeAt(i));
  }
  text(0, "RIFF");
  view.setUint32(4, size + 36, true);
  text(8, "WAVE");
  text(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, size, true);
  return new Blob([header, ...chunks], { type: "audio/wav" });
}
