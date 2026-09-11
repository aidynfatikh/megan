import type { components } from "./generated/schema";

export type Job = components["schemas"]["Job"];
export type Report = components["schemas"]["Report"];
export type Action = components["schemas"]["Action"];
export type Claim = components["schemas"]["Claim"];
export type Source = components["schemas"]["Source"];
export type ActionPatch = components["schemas"]["ActionPatch"];
export type Health = {
  ready: boolean;
  database: boolean;
  asr: boolean;
  ollama: boolean;
  ffmpeg: boolean;
  busy: boolean;
  local_only: boolean;
  asr_backend: string;
  asr_model: string;
  llm: string;
  diarization: string;
  diarization_ready: boolean;
  chat_enabled: boolean;
  max_upload_mb: number;
  max_duration_sec: number;
};
export type Answer = {
  answer: string;
  citations: Source[];
  supported: boolean;
};
