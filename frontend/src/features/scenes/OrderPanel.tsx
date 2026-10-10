import type { SceneInfo, SlotValue } from "../../types/messages";

const SLOT_LABELS: Record<string, string> = {
  drink: "음료",
  size: "크기",
  temperature: "온도",
  milk: "우유",
  extra_shots: "추가 샷",
};

const PHASE_LABELS: Record<string, string> = {
  greeting: "인사",
  ordering: "주문 중",
  clarifying: "확인 필요",
  confirming: "주문 확인",
  completed: "완료",
  cancelled: "종료",
};

interface Props {
  scene: SceneInfo;
  phase: string;
  slots: Record<string, SlotValue>;
}

function display(value: SlotValue): string {
  if (value === null || value === undefined) return "—";
  return String(value).replace(/_/g, " ");
}

export function OrderPanel({ scene, phase, slots }: Props) {
  const rows = [
    ...scene.required_slots.map((s) => ({ slot: s, required: true })),
    ...scene.optional_slots.map((s) => ({ slot: s, required: false })),
  ];
  return (
    <aside className="order-panel" aria-label="주문 상태">
      <div className="panel-head">
        <h2>주문 상태</h2>
        <span className={`phase phase-${phase}`}>{PHASE_LABELS[phase] ?? phase}</span>
      </div>
      <dl className="slots">
        {rows.map(({ slot, required }) => {
          const value = slots[slot];
          const filled = value !== null && value !== undefined;
          return (
            <div key={slot} className={`slot${filled ? " filled" : ""}`}>
              <dt>
                {SLOT_LABELS[slot] ?? slot}
                {required && <span className="req">필수</span>}
              </dt>
              <dd>{display(value)}</dd>
            </div>
          );
        })}
      </dl>
    </aside>
  );
}
