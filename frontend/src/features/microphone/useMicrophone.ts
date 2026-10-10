import type { MicVAD } from "@ricky0123/vad-web";
import { useCallback, useEffect, useRef, useState } from "react";

export type MicStatus = "off" | "loading" | "listening" | "hearing" | "paused" | "error";

const ASSET_PATH = `${import.meta.env.BASE_URL}vad/`;

interface Options {
  /** One finished utterance, 16 kHz mono float samples (cut by Silero VAD). */
  onUtterance: (samples: Float32Array) => void;
  /** Pause listening while this is true (e.g. the NPC is talking or a reply is pending). */
  hold: boolean;
}

export function useMicrophone({ onUtterance, hold }: Options) {
  const [status, setStatus] = useState<MicStatus>("off");
  const [error, setError] = useState<string | null>(null);
  const vad = useRef<MicVAD | null>(null);
  const callback = useRef(onUtterance);
  callback.current = onUtterance;

  const start = useCallback(async () => {
    if (vad.current) return;
    setError(null);
    setStatus("loading");
    try {
      const { MicVAD } = await import("@ricky0123/vad-web");
      const instance = await MicVAD.new({
        model: "v5",
        baseAssetPath: ASSET_PATH,
        onnxWASMBasePath: ASSET_PATH,
        positiveSpeechThreshold: 0.5,
        negativeSpeechThreshold: 0.35,
        redemptionMs: 700, // silence that ends an utterance
        preSpeechPadMs: 300,
        minSpeechMs: 250,
        startOnLoad: false,
        onSpeechStart: () => setStatus("hearing"),
        onVADMisfire: () => setStatus("listening"),
        onSpeechEnd: (audio: Float32Array) => {
          setStatus("listening");
          callback.current(audio);
        },
      });
      vad.current = instance;
      await instance.start();
      setStatus("listening");
    } catch (e) {
      vad.current = null;
      const name = e instanceof DOMException ? e.name : "";
      setError(
        name === "NotAllowedError"
          ? "마이크 권한이 거부됐어요. 브라우저 주소창의 권한 설정에서 허용해 주세요."
          : name === "NotFoundError"
            ? "마이크를 찾을 수 없어요."
            : `마이크를 시작하지 못했어요 (${e instanceof Error ? e.message : String(e)}).`,
      );
      setStatus("error");
    }
  }, []);

  const stop = useCallback(async () => {
    const instance = vad.current;
    vad.current = null;
    setStatus("off");
    await instance?.destroy();
  }, []);

  // Don't record the NPC's own voice or talk over a pending reply.
  useEffect(() => {
    const instance = vad.current;
    if (!instance) return;
    if (hold && instance.listening) {
      void instance.pause();
      setStatus("paused");
    } else if (!hold && !instance.listening) {
      void instance.start().then(() => setStatus("listening"));
    }
  }, [hold, status]);

  useEffect(() => () => void vad.current?.destroy(), []);

  return { status, error, start, stop, active: status !== "off" && status !== "error" };
}
