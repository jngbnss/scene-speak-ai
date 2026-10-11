import type { Feedback, ReportEntry, ReviewData, ShadowResult } from "../types/messages";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export const fetchFeedback = (sessionId: string) =>
  getJson<Feedback>(`/api/sessions/${encodeURIComponent(sessionId)}/feedback`);

export const fetchReview = (userId: number) => getJson<ReviewData>(`/api/users/${userId}/review`);

export const utteranceAudioUrl = (sessionId: string, seq: number) =>
  `/api/sessions/${encodeURIComponent(sessionId)}/utterances/${seq}/audio`;

export const checkShadowing = (
  reference: string,
  input: { pcm16_base64: string; sample_rate: number } | { text: string },
) => postJson<ShadowResult>("/api/shadowing", { reference, ...input });

export const fetchReports = () => getJson<ReportEntry[]>("/api/reports");

export const fetchReport = (name: string) =>
  getJson<Record<string, unknown>>(`/api/reports/${encodeURIComponent(name)}`);
