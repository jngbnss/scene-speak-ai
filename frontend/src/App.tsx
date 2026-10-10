import { useState, type FormEvent } from "react";

import { ConversationView } from "./features/conversation/ConversationView";
import { useConversation } from "./features/conversation/useConversation";
import { FeedbackView } from "./features/feedback/FeedbackView";
import { ReviewView } from "./features/feedback/ReviewView";
import { OrderPanel } from "./features/scenes/OrderPanel";

const NICKNAME_KEY = "scenespeak.nickname";

const END_REASONS: Record<string, string> = {
  completed: "주문을 완료했어요.",
  user_cancelled: "주문을 취소했어요.",
  user_ended: "대화를 종료했어요.",
  max_user_turns: "대화가 너무 길어져 종료됐어요.",
};

function loadNickname(): string {
  try {
    return localStorage.getItem(NICKNAME_KEY) ?? "";
  } catch {
    return "";
  }
}

function NicknameGate({ onDone }: { onDone: (name: string) => void }) {
  const [name, setName] = useState(loadNickname());
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const n = name.trim();
    if (!n) return;
    try {
      localStorage.setItem(NICKNAME_KEY, n);
    } catch {
      // storage blocked; the nickname still works for this visit
    }
    onDone(n);
  };
  return (
    <div className="gate">
      <p className="eyebrow">SceneSpeak</p>
      <h1>뉴욕 카페에서 영어로 주문해 보세요</h1>
      <p className="muted">닉네임별로 대화 기록과 복습 문장이 저장됩니다.</p>
      <form onSubmit={submit} className="composer">
        <label htmlFor="nickname" className="visually-hidden">
          닉네임
        </label>
        <input
          id="nickname"
          value={name}
          maxLength={40}
          onChange={(e) => setName(e.target.value)}
          placeholder="닉네임 (예: mina)"
          autoFocus
        />
        <button type="submit" disabled={!name.trim()}>
          시작하기
        </button>
      </form>
    </div>
  );
}

function Scene({ nickname, onLogout }: { nickname: string; onLogout: () => void }) {
  const { state, status, say, fix, end, restart } = useConversation(nickname);
  const [tab, setTab] = useState<"talk" | "review">("talk");
  const { scene, result } = state;
  const ended = result !== null;

  return (
    <div className="app">
      <header className="top">
        <div>
          <p className="eyebrow">{scene?.place ?? "SceneSpeak"}</p>
          <h1>{scene?.title ?? "연결 중…"}</h1>
          {scene && (
            <p className="goal">
              목표: {scene.goal_ko} · 역할: {scene.user_role}
            </p>
          )}
        </div>
        <div className="top-actions">
          <span className={`status status-${status}`}>
            {status === "open" ? "연결됨" : status === "connecting" ? "연결 중" : "연결 끊김"}
          </span>
          <span className="muted">{nickname}</span>
          <button className="link" onClick={onLogout}>
            바꾸기
          </button>
        </div>
      </header>

      <nav className="tabs" aria-label="화면">
        <button aria-pressed={tab === "talk"} onClick={() => setTab("talk")}>
          대화
        </button>
        <button
          aria-pressed={tab === "review"}
          onClick={() => setTab("review")}
          disabled={state.userId === null}
        >
          복습
        </button>
      </nav>

      {tab === "review" && state.userId !== null ? (
        <ReviewView key={`${state.userId}-${state.feedback}`} userId={state.userId} />
      ) : (
        <>
          {status === "closed" && !scene && (
            <p className="banner error">
              서버에 연결할 수 없어요. 백엔드가 실행 중인지 확인해 주세요 (README의 실행 방법 참고).
            </p>
          )}
          {state.error && <p className="banner error">{state.error}</p>}
          {result && (
            <div className={`banner ${result.success ? "success" : "neutral"}`}>
              <span>
                {result.success ? "✓ 과업 성공 · " : "과업 미완료 · "}
                {END_REASONS[result.reason ?? ""] ?? result.reason}
              </span>
              <button onClick={restart}>다시 하기</button>
            </div>
          )}

          <main className="layout">
            <ConversationView
              lines={state.lines}
              disabled={status !== "open" || !scene || ended}
              waiting={state.waitingForNpc}
              canFix={!ended}
              onSay={say}
              onFix={fix}
            />
            <div className="side">
              {scene && <OrderPanel scene={scene} phase={state.phase} slots={state.slots} />}
              {!ended && scene && (
                <button className="end-btn" onClick={end}>
                  대화 끝내기
                </button>
              )}
            </div>
          </main>

          {state.sessionId && state.feedback !== "none" && (
            <FeedbackView sessionId={state.sessionId} status={state.feedback} />
          )}
        </>
      )}
    </div>
  );
}

export function App() {
  const [nickname, setNickname] = useState<string | null>(null);
  if (!nickname) return <NicknameGate onDone={setNickname} />;
  return <Scene key={nickname} nickname={nickname} onLogout={() => setNickname(null)} />;
}
