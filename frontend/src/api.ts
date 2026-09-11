import type { ActionPatch, Answer, Health, Job } from "./types";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const timeout = AbortSignal.timeout(
    path.endsWith("/chat")
      ? 240000
      : options?.method === "POST"
        ? 120000
        : 20000,
  );
  const signal = options?.signal
    ? AbortSignal.any([options.signal, timeout])
    : timeout;
  const response = await fetch(`/api${path}`, { ...options, signal });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((e: { msg: string }) => e.msg).join("; ")
          : `Request failed (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: (signal?: AbortSignal) => request<Health>("/health", { signal }),
  jobs: (signal?: AbortSignal) => request<Job[]>("/jobs", { signal }),
  job: (id: string, signal?: AbortSignal) =>
    request<Job>(`/jobs/${id}`, { signal }),
  example: (signal?: AbortSignal) => request<Job>("/example", { signal }),
  upload: (file: File, meetingDate: string, language: string) => {
    const data = new FormData();
    data.append("file", file);
    if (meetingDate) data.append("meeting_date", meetingDate);
    data.append("report_language", language);
    return request<Job>("/jobs", { method: "POST", body: data });
  },
  retry: (id: string) => request<Job>(`/jobs/${id}/retry`, { method: "POST" }),
  editAction: (id: string, itemId: string, patch: ActionPatch) =>
    request<Job>(`/jobs/${id}/action-items/${itemId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }),
  chat: (id: string, question: string) =>
    request<Answer>(`/jobs/${id}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }),
};

export function timestamp(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  const total = Math.floor(seconds);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "Date not provided";
  return new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString(
    "en-GB",
    { day: "numeric", month: "short", year: "numeric" },
  );
}
