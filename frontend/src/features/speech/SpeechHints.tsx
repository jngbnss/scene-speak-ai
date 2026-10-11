import { Fragment, useEffect, useRef, useState } from "react";

import { utteranceAudioUrl } from "../../services/api";
import { playClip } from "../../services/audio";
import type { LineSpeech } from "../../types/messages";
import { seconds, segmentReason } from "./format";

interface Props {
  sessionId: string;
  lines: LineSpeech[];
  longPauseMs?: number;
}

/** "Listen again": the user's own recording, with long pauses and unsure words marked. */
export function SpeechHints({ sessionId, lines, longPauseMs = 800 }: Props) {
  const [playing, setPlaying] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);
  const stop = useRef<(() => void) | null>(null);

  useEffect(() => () => stop.current?.(), []);

  const play = (key: string, seq: number, start: number, end: number) => {
    stop.current?.();
    if (playing === key) return;
    setPlaying(key);
    const url = utteranceAudioUrl(sessionId, seq);
    stop.current = playClip(url, start, end, (loaded) => {
      setPlaying((k) => (k === key ? null : k));
      stop.current = null;
      if (!loaded) setMissing(true);
    });
  };

  const withHints = lines.filter((l) => l.segments.length > 0).length;

  return (
    <article className="card speech-card">
      <h3>다시 들어볼 구간</h3>
      <p className="muted">
        {withHints === 0
          ? "길게 멈춘 곳이나 인식이 불확실한 단어가 없었어요. 내 목소리를 다시 들어 볼 수 있어요."
          : `${(longPauseMs / 1000).toFixed(1)}초 이상 멈춘 곳과 인식이 불확실한 단어를 표시했어요.`}
      </p>
      {missing && <p className="banner error">녹음이 보관 기간이 지나 삭제됐어요.</p>}
      {lines.map((line) => {
        const whole = `${line.utterance_seq}-all`;
        return (
          <div key={line.utterance_seq} className="speech-line">
            <p className="speech-words">
              <button
                className="play"
                aria-label={`${line.text} 전체 듣기`}
                aria-pressed={playing === whole}
                onClick={() => play(whole, line.utterance_seq, 0, line.duration_s)}
              >
                {playing === whole ? "■" : "▶"}
              </button>
              {line.words.map((w, i) => (
                <Fragment key={i}>
                  {i > 0 && w.pause_before_ms >= longPauseMs && (
                    <span className="pause-mark" title="멈춘 시간">
                      ‖ {seconds(w.pause_before_ms / 1000)}
                    </span>
                  )}
                  {w.uncertain ? <mark className="uncertain">{w.word}</mark> : <span>{w.word}</span>}{" "}
                </Fragment>
              ))}
            </p>
            {line.segments.map((seg, i) => {
              const key = `${line.utterance_seq}-${i}`;
              return (
                <button
                  key={key}
                  className="segment"
                  aria-pressed={playing === key}
                  onClick={() => play(key, line.utterance_seq, seg.start, seg.end)}
                >
                  {playing === key ? "■" : "▶"} “{seg.text}”{" "}
                  <span className="muted">
                    {seconds(seg.start)}–{seconds(seg.end)} · {segmentReason(seg)}
                  </span>
                </button>
              );
            })}
          </div>
        );
      })}
    </article>
  );
}
