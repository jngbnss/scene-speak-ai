import { useEffect, useRef, useState, type FormEvent } from "react";

import type { ChatLine } from "./conversationReducer";

interface Props {
  lines: ChatLine[];
  disabled: boolean;
  waiting: boolean;
  canFix: boolean;
  onSay: (text: string) => void;
  onFix: (seq: number, text: string) => void;
}

function UserLine({ line, canFix, onFix }: { line: ChatLine; canFix: boolean; onFix: Props["onFix"] }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(line.text);

  if (editing) {
    return (
      <form
        className="fix-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (draft.trim() && draft.trim() !== line.text) onFix(line.seq, draft.trim());
          setEditing(false);
        }}
      >
        <label htmlFor={`fix-${line.seq}`} className="visually-hidden">
          인식된 문장 고치기
        </label>
        <input id={`fix-${line.seq}`} value={draft} onChange={(e) => setDraft(e.target.value)} autoFocus />
        <button type="submit">저장</button>
        <button type="button" onClick={() => setEditing(false)}>
          취소
        </button>
      </form>
    );
  }
  return (
    <>
      <span className="who">You</span>
      {line.text}
      {canFix && (
        <button
          className="link fix-btn"
          onClick={() => {
            setDraft(line.text);
            setEditing(true);
          }}
          title="내가 말한 것과 다르게 인식됐다면 고쳐 주세요. 피드백은 고친 문장으로 만들어집니다."
        >
          고치기
        </button>
      )}
    </>
  );
}

export function ConversationView({ lines, disabled, waiting, canFix, onSay, onFix }: Props) {
  const [draft, setDraft] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [lines.length, waiting]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text || waiting) return;
    onSay(text);
    setDraft("");
  };

  return (
    <section className="conversation" aria-label="대화">
      <ol className="chat">
        {lines.map((line) => (
          <li key={line.id} className={`bubble ${line.speaker}`}>
            {line.speaker === "npc" ? (
              <>
                <span className="who">Barista</span>
                {line.text}
              </>
            ) : (
              <UserLine line={line} canFix={canFix} onFix={onFix} />
            )}
          </li>
        ))}
        {waiting && (
          <li className="bubble npc typing" aria-live="polite">
            <span className="who">Barista</span>…
          </li>
        )}
      </ol>
      <div ref={bottom} />
      <form className="composer" onSubmit={submit}>
        <label htmlFor="utterance" className="visually-hidden">
          영어로 말하기
        </label>
        <input
          id="utterance"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Type in English, e.g. Can I get a large hot latte?"
          autoComplete="off"
          disabled={disabled}
        />
        <button type="submit" disabled={disabled || waiting || !draft.trim()}>
          보내기
        </button>
      </form>
    </section>
  );
}
