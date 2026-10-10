import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { NpcVoice, float32ToPcm16Base64 } from "../../services/audio";
import { SessionSocket, defaultSocketUrl, type SocketStatus } from "../../services/sessionSocket";
import { conversationReducer, initialConversation } from "./conversationReducer";

const VAD_SAMPLE_RATE = 16000;

export function useConversation(nickname: string, sceneId?: string) {
  const [state, dispatch] = useReducer(conversationReducer, initialConversation);
  const [status, setStatus] = useState<SocketStatus>("connecting");
  const [npcSpeaking, setNpcSpeaking] = useState(false);
  const [muted, setMuted] = useState(false);
  const socket = useRef<SessionSocket | null>(null);
  const voice = useRef<NpcVoice | null>(null);
  const seq = useRef(0);

  if (!voice.current) voice.current = new NpcVoice(setNpcSpeaking);

  const start = useCallback(() => {
    socket.current?.close();
    voice.current?.stop();
    seq.current = 0;
    dispatch({ type: "reset" });
    const s = new SessionSocket(
      defaultSocketUrl(),
      (msg) => {
        if (msg.type === "npc_audio") voice.current?.enqueue(msg.data_base64);
        dispatch({ type: "server", msg });
      },
      setStatus,
    );
    socket.current = s;
    s.connect(() => s.send({ type: "session_start", scene_id: sceneId, nickname }));
  }, [nickname, sceneId]);

  useEffect(() => {
    start();
    return () => {
      socket.current?.close();
      voice.current?.stop();
    };
  }, [start]);

  const say = useCallback((text: string) => {
    seq.current += 1;
    dispatch({ type: "user_sent" });
    socket.current?.send({ type: "text_utterance", seq: seq.current, text });
  }, []);

  const sayAudio = useCallback((samples: Float32Array) => {
    seq.current += 1;
    dispatch({ type: "user_sent" });
    socket.current?.send({
      type: "audio_utterance",
      seq: seq.current,
      sample_rate: VAD_SAMPLE_RATE,
      pcm16_base64: float32ToPcm16Base64(samples),
    });
  }, []);

  const fix = useCallback((lineSeq: number, corrected: string) => {
    socket.current?.send({ type: "transcript_fix", seq: lineSeq, corrected_text: corrected });
  }, []);

  const end = useCallback(() => socket.current?.send({ type: "session_end", reason: "user" }), []);

  const toggleMute = useCallback(() => {
    const v = voice.current;
    if (!v) return;
    v.muted = !v.muted;
    if (v.muted) v.stop();
    setMuted(v.muted);
  }, []);

  return {
    state,
    status,
    npcSpeaking,
    muted,
    say,
    sayAudio,
    fix,
    end,
    toggleMute,
    restart: start,
  };
}
