import type { MicStatus } from "./useMicrophone";

const LABELS: Record<MicStatus, string> = {
  off: "말하기",
  loading: "준비 중…",
  listening: "듣는 중",
  hearing: "말하는 중…",
  paused: "잠시 멈춤",
  error: "다시 시도",
};

interface Props {
  status: MicStatus;
  disabled: boolean;
  onStart: () => void;
  onStop: () => void;
}

export function MicButton({ status, disabled, onStart, onStop }: Props) {
  const on = status !== "off" && status !== "error";
  return (
    <button
      type="button"
      className={`mic mic-${status}`}
      aria-pressed={on}
      disabled={disabled || status === "loading"}
      onClick={on ? onStop : onStart}
      title={on ? "마이크 끄기" : "마이크를 켜고 영어로 말해 보세요. 말을 멈추면 자동으로 보냅니다."}
    >
      <span className="mic-dot" aria-hidden="true" />
      {LABELS[status]}
    </button>
  );
}
