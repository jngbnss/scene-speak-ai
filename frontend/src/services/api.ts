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

export const login = (nickname: string) => postJson<{ user_id: number }>("/api/users", { nickname });

// Without a backend (GitHub Pages) the report reads the copies made at build time
// (scripts/copy-reports.mjs).
const STATIC_REPORTS = `${import.meta.env.BASE_URL}reports/`;

async function withStaticFallback<T>(api: string, file: string): Promise<T> {
  try {
    return await getJson<T>(api);
  } catch {
    return await getJson<T>(STATIC_REPORTS + file);
  }
}

export const fetchReports = () => withStaticFallback<ReportEntry[]>("/api/reports", "index.json");

export const fetchReport = (name: string) =>
  withStaticFallback<Record<string, unknown>>(
    `/api/reports/${encodeURIComponent(name)}`,
    encodeURIComponent(name),
  );
