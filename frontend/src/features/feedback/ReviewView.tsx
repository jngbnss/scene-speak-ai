import { useEffect, useState } from "react";

import { fetchReview } from "../../services/api";
import type { ReviewData } from "../../types/messages";
import { ShadowPractice } from "../speech/ShadowPractice";

export function ReviewView({ userId }: { userId: number }) {
  const [data, setData] = useState<ReviewData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [practicing, setPracticing] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchReview(userId)
      .then((d) => !cancelled && setData(d))
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [userId]);

  if (error) return <p className="banner error">복습 기록을 불러오지 못했어요 ({error}).</p>;
  if (!data) return <p className="muted">불러오는 중…</p>;

  const done = data.sessions.filter((s) => s.success).length;

  return (
    <section className="review" aria-label="복습">
      <div className="review-head">
        <h2>{data.nickname}님의 복습</h2>
        <p className="muted">
          대화 {data.sessions.length}회 · 주문 성공 {done}회
        </p>
      </div>

      <div className="cards">
        <article className="card">
          <h3>자주 틀린 부분</h3>
          {data.repeated_errors.length === 0 ? (
            <p className="muted">두 번 이상 반복된 실수가 아직 없어요.</p>
          ) : (
            data.repeated_errors.map((e) => (
              <div key={e.error_type} className="correction">
                <p>
                  <span className="tag">{e.error_type}</span> {e.count}회
                </p>
                {e.examples.map((x, i) => (
                  <p key={i}>
                    <span className="strike">{x.original}</span> → <span className="fix">{x.corrected}</span>
                  </p>
                ))}
              </div>
            ))
          )}
        </article>

        <article className="card">
          <h3>복습 문장</h3>
          {data.review_items.length === 0 ? (
            <p className="muted">대화를 마치면 여기에 연습할 문장이 쌓여요.</p>
          ) : (
            <>
              <p className="muted">문장을 골라 소리 내어 읽으면 빠지거나 덧붙인 단어를 알려 드려요.</p>
              <ul className="sentences">
                {data.review_items.map((r) => (
                  <li key={r.sentence}>
                    {r.sentence}
                    {r.times > 1 && <span className="muted"> ×{r.times}</span>}{" "}
                    {practicing === r.sentence ? (
                      <ShadowPractice sentence={r.sentence} onClose={() => setPracticing(null)} />
                    ) : (
                      <button className="link" onClick={() => setPracticing(r.sentence)}>
                        따라 말하기
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </>
          )}
        </article>
      </div>
    </section>
  );
}
