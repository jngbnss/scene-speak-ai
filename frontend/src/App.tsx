import { ConversationView } from "./features/conversation/ConversationView";
import { useConversation } from "./features/conversation/useConversation";
import { OrderPanel } from "./features/scenes/OrderPanel";

const END_REASONS: Record<string, string> = {
  completed: "주문을 완료했어요.",
  user_cancelled: "주문을 취소했어요.",
  user_ended: "대화를 종료했어요.",
  max_user_turns: "대화가 너무 길어져 종료됐어요.",
};

export function App() {
  const { state, status, say, end, restart } = useConversation();
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
          {ended || status === "closed" ? (
            <button onClick={restart}>다시 시작</button>
          ) : (
            <button onClick={end} disabled={!scene}>
              대화 끝내기
            </button>
          )}
        </div>
      </header>

      {status === "closed" && !scene && (
        <p className="banner error">
          서버에 연결할 수 없어요. 백엔드가 실행 중인지 확인해 주세요 (README의 실행 방법 참고).
        </p>
      )}
      {state.error && <p className="banner error">{state.error}</p>}
      {result && (
        <p className={`banner ${result.success ? "success" : "neutral"}`}>
          {result.success ? "✓ 과업 성공 · " : "과업 미완료 · "}
          {END_REASONS[result.reason ?? ""] ?? result.reason}
        </p>
      )}

      <main className="layout">
        <ConversationView
          lines={state.lines}
          disabled={status !== "open" || !scene || ended}
          onSay={say}
        />
        {scene && <OrderPanel scene={scene} phase={state.phase} slots={state.slots} />}
      </main>
    </div>
  );
}
