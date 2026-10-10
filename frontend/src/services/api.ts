import type { Feedback, ReviewData } from "../types/messages";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export const fetchFeedback = (sessionId: string) =>
  getJson<Feedback>(`/api/sessions/${encodeURIComponent(sessionId)}/feedback`);

export const fetchReview = (userId: number) => getJson<ReviewData>(`/api/users/${userId}/review`);
