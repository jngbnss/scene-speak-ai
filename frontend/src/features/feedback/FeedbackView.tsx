import { useEffect, useState } from "react";

import { fetchFeedback } from "../../services/api";
import type { Feedback } from "../../types/messages";
import { SpeechHints } from "../speech/SpeechHints";

interface Props {
  sessionId: string;
  status: "none" | "pending" | "ready";
}

export function FeedbackView({ sessionId, status }: Props) {
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "ready") return;
    let cancelled = false;
    fetchFeedback(sessionId)
      .then((f) => !cancelled && setFeedback(f))
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [sessionId, status]);

  if (status === "pending" || (status === "ready" && !feedback && !error)) {
    return (
      <section className="feedback" aria-busy="true">
        <h2>피드백</h2>
        <p className="muted">대화를 분석하고 있어요. 몇 초 걸립니다…</p>
      </section>
    );
  }
  if (error) {
    return (
      <section className="feedback">
        <h2>피드백</h2>
        <p className="banner error">피드백을 불러오지 못했어요 ({error}).</p>
      </section>
    );
  }
  if (!feedback) return null;

  const noIssues = feedback.grammar_errors.length === 0 && feedback.unnatural_expressions.length === 0;

  return (
    <section className="feedback" aria-label="피드백">
      <h2>피드백</h2>
      {feedback.summary && <p className="summary">{feedback.summary}</p>}

      <div className="cards">
        <article className="card">
          <h3>과업 결과</h3>
          <p className={feedback.task_success ? "ok" : "warn"}>
            {feedback.task_success ? "주문 성공" : "주문 미완료"}
          </p>
          {feedback.missed_information.length > 0 && (
            <p className="muted">빠진 정보: {feedback.missed_information.join(", ")}</p>
          )}
        </article>

        <article className="card">
          <h3>문법 · 표현</h3>
          {noIssues && <p className="muted">고칠 부분을 찾지 못했어요.</p>}
          {feedback.grammar_errors.map((e, i) => (
            <div key={`g${i}`} className="correction">
              <p>
                <span className="strike">{e.original}</span>
                <br />
                <span className="fix">{e.corrected}</span>
              </p>
              <p className="muted">
                <span className="tag">{e.type}</span> {e.explanation_ko}
              </p>
            </div>
          ))}
          {feedback.unnatural_expressions.map((e, i) => (
            <div key={`u${i}`} className="correction">
              <p>
                <span className="strike soft">{e.original}</span>
                <br />
                <span className="fix">{e.better}</span>
              </p>
              <p className="muted">
                <span className="tag">더 자연스럽게</span> {e.reason_ko}
              </p>
            </div>
          ))}
        </article>

        {feedback.speech.length > 0 && (
          <SpeechHints sessionId={sessionId} lines={feedback.speech} />
        )}

        {feedback.speech.length === 0 && feedback.uncertain_spans.length > 0 && (
          <article className="card">
            <h3>다시 들어볼 부분</h3>
            {feedback.uncertain_spans.map((u, i) => (
              <p key={i}>
                <b>“{u.word}”</b>{" "}
                <span className="muted">인식 신뢰도 {u.confidence.toFixed(2)}</span>
              </p>
            ))}
            <p className="muted">인식이 불확실한 단어라서 문법 지적에서 뺐어요.</p>
          </article>
        )}

        <article className="card">
          <h3>복습 문장</h3>
          {feedback.review_items.length === 0 ? (
            <p className="muted">저장할 복습 문장이 없어요.</p>
          ) : (
            <ul className="sentences">
              {feedback.review_items.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          )}
          {feedback.recommended_sentences.length > 0 && (
            <>
              <h4>다음에 써 볼 문장</h4>
              <ul className="sentences">
                {feedback.recommended_sentences.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ul>
            </>
          )}
        </article>
      </div>
      {feedback.source === "default" && (
        <p className="muted">AI 분석에 실패해 기본 결과를 보여드려요.</p>
      )}
    </section>
  );
}
