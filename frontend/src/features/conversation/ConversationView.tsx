import { useEffect, useRef, useState, type FormEvent } from "react";

import type { ChatLine } from "./conversationReducer";

interface Props {
  lines: ChatLine[];
  disabled: boolean;
  onSay: (text: string) => void;
}

export function ConversationView({ lines, disabled, onSay }: Props) {
  const [draft, setDraft] = useState("");
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [lines.length]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text) return;
    onSay(text);
    setDraft("");
  };

  return (
    <section className="conversation" aria-label="대화">
      <ol className="chat">
        {lines.map((line) => (
          <li key={line.id} className={`bubble ${line.speaker}`}>
            <span className="who">{line.speaker === "npc" ? "Barista" : "You"}</span>
            {line.text}
          </li>
        ))}
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
        <button type="submit" disabled={disabled || !draft.trim()}>
          보내기
        </button>
      </form>
    </section>
  );
}
