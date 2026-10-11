import { useEffect, useRef } from "react";

import { FeedbackView } from "../feedback/FeedbackView";
import { useMicrophone } from "../microphone/useMicrophone";
import { OrderPanel } from "../scenes/OrderPanel";
import { ConversationView } from "./ConversationView";
import { useConversation } from "./useConversation";

const END_REASONS: Record<string, string> = {
  completed: "목표를 모두 해냈어요.",
  user_cancelled: "주문을 취소했어요.",
  user_ended: "대화를 종료했어요.",
  max_user_turns: "대화가 너무 길어져 종료됐어요.",
};

interface Props {
  nickname: string;
  sceneId: string;
  /** Who the player walked up to, shown before the server answers. */
  npcName?: string;
  example?: string;
  muted: boolean;
  onClose: () => void;
  onUserId: (id: number) => void;
  onFinished: (sceneId: string, success: boolean) => void;
}

/** One conversation with one NPC: transcript, mic, task panel, then feedback. */
export function ConversationScreen({ nickname, sceneId, npcName, example, muted, onClose, onUserId, onFinished }: Props) {
  const { state, status, npcSpeaking, muted: voiceMuted, say, sayAudio, fix, end, toggleMute, restart } =
    useConversation(nickname, sceneId);
  const { scene, result } = state;
  const ended = result !== null;
  const mic = useMicrophone({
    onUtterance: sayAudio,
    hold: npcSpeaking || state.waitingForNpc || ended,
  });
  const reported = useRef(false);

  useEffect(() => {
    if (voiceMuted !== muted) toggleMute();
  }, [muted, voiceMuted, toggleMute]);

  useEffect(() => {
    if (state.userId !== null) onUserId(state.userId);
  }, [state.userId, onUserId]);

  useEffect(() => {
    if (result && !reported.current) {
      reported.current = true;
      onFinished(sceneId, result.success);
    }
    if (!result) reported.current = false;
  }, [result, sceneId, onFinished]);

  return (
    <div className="conversation-screen">
      <div className="scene-head">
        <div>
          <p className="eyebrow">{scene?.place ?? npcName ?? "SceneSpeak"}</p>
          <h2>{scene?.title ?? "연결 중…"}</h2>
          {scene && (
            <p className="goal">
              목표: {scene.goal_ko} · 내 역할: {scene.user_role}
            </p>
          )}
        </div>
        <div className="top-actions">
          <span className={`status status-${status}`}>
            {status === "open" ? "연결됨" : status === "connecting" ? "연결 중" : "연결 끊김"}
          </span>
          <button className="back-btn" onClick={onClose}>
            ← 거리로 돌아가기
          </button>
        </div>
      </div>

      {status === "closed" && !scene && (
        <p className="banner error">
          서버에 연결할 수 없어요. 대화하려면 백엔드가 실행 중이어야 해요 (README의 실행 방법 참고).
        </p>
      )}
      {state.error && <p className="banner error">{state.error}</p>}
      {result && (
        <div className={`banner ${result.success ? "success" : "neutral"}`}>
          <span>
            {result.success ? "✓ 미션 성공 · " : "미션 미완료 · "}
            {END_REASONS[result.reason ?? ""] ?? result.reason}
          </span>
          <span className="banner-actions">
            <button onClick={restart}>다시 하기</button>
            <button onClick={onClose}>거리로</button>
          </span>
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
          npcLabel={npcName ?? "Barista"}
          example={example}
          mic={{ status: mic.status, error: mic.error, start: mic.start, stop: mic.stop }}
        />
        <div className="side">
          {scene && <OrderPanel scene={scene} phase={state.phase} slots={state.slots} />}
          {state.timing && (
            <p className="timing" title="말이 끝난 뒤 NPC 음성이 준비되기까지">
              응답 {(state.timing.total_ms / 1000).toFixed(1)}초 · 인식 {(state.timing.stt_ms / 1000).toFixed(1)} · 대사{" "}
              {(state.timing.npc_ms / 1000).toFixed(1)} · 음성 {(state.timing.tts_ms / 1000).toFixed(1)}
            </p>
          )}
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
    </div>
  );
}
