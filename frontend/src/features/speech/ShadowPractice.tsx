import { useId, useState, type FormEvent } from "react";

import { checkShadowing } from "../../services/api";
import { float32ToPcm16Base64 } from "../../services/audio";
import type { ShadowResult } from "../../types/messages";
import { useMicrophone } from "../microphone/useMicrophone";
import { seconds, shadowSummary } from "./format";

const STATUS_LABEL = { ok: "", missing: "빠짐", extra: "덧붙임", unclear: "불확실" } as const;

/** Read a review sentence aloud; shows missing and extra words against the sentence. */
export function ShadowPractice({ sentence, onClose }: { sentence: string; onClose: () => void }) {
  const [result, setResult] = useState<ShadowResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const inputId = useId();

  const submit = async (input: Parameters<typeof checkShadowing>[1]) => {
    setBusy(true);
    setError(null);
    try {
      setResult(await checkShadowing(sentence, input));
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setError(
        message.startsWith("503")
          ? "음성 인식이 꺼져 있어요. 아래에 입력해서 확인할 수 있어요."
          : `확인하지 못했어요 (${message}).`,
      );
    } finally {
      setBusy(false);
    }
  };

  const mic = useMicrophone({
    hold: busy,
    onUtterance: (samples) => {
      void mic.stop();
      void submit({ pcm16_base64: float32ToPcm16Base64(samples), sample_rate: 16000 });
    },
  });

  const onType = (e: FormEvent) => {
    e.preventDefault();
    if (typed.trim()) void submit({ text: typed.trim() });
  };

  const pauses = result?.speech?.long_pauses_ms ?? [];
  const micLabel =
    mic.status === "loading"
      ? "준비 중…"
      : mic.active
        ? mic.status === "hearing"
          ? "듣는 중…"
          : "말해 보세요"
        : "소리 내어 읽기";

  return (
    <div className="shadow" role="group" aria-label="따라 말하기">
      <p className="shadow-target">{sentence}</p>
      <div className="shadow-actions">
        <button
          className={`mic mic-${mic.status}`}
          aria-pressed={mic.active}
          disabled={busy}
          onClick={() => void (mic.active ? mic.stop() : mic.start())}
        >
          <span className="mic-dot" aria-hidden="true" />
          {micLabel}
        </button>
        <button className="link" onClick={onClose}>
          닫기
        </button>
      </div>
      {mic.error && <p className="banner error">{mic.error}</p>}
      {error && <p className="banner error">{error}</p>}
      {busy && <p className="muted">확인하는 중…</p>}
      {result && (
        <div className="shadow-result" aria-live="polite">
          <p>{shadowSummary(result)}</p>
          <p className="shadow-words">
            {result.words.map((w, i) => (
              <span key={i} className={`sw sw-${w.status}`}>
                {w.word}
                {w.status !== "ok" && <small> ({STATUS_LABEL[w.status]})</small>}
              </span>
            ))}
          </p>
          <p className="muted">
            들린 문장: “{result.heard || "—"}”
            {pauses.length > 0 &&
              ` · 길게 멈춘 곳 ${pauses.map((ms) => seconds(ms / 1000)).join(", ")}`}
          </p>
        </div>
      )}
      <form className="fix-form" onSubmit={onType}>
        <label className="visually-hidden" htmlFor={inputId}>
          마이크 없이 입력해서 확인
        </label>
        <input
          id={inputId}
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          placeholder="마이크 없이 입력해서 확인"
          maxLength={300}
        />
        <button type="submit" disabled={busy || !typed.trim()}>
          확인
        </button>
      </form>
    </div>
  );
}
