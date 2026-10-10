import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { SessionSocket, defaultSocketUrl, type SocketStatus } from "../../services/sessionSocket";
import { conversationReducer, initialConversation } from "./conversationReducer";

export function useConversation(sceneId?: string) {
  const [state, dispatch] = useReducer(conversationReducer, initialConversation);
  const [status, setStatus] = useState<SocketStatus>("connecting");
  const socket = useRef<SessionSocket | null>(null);
  const seq = useRef(0);

  const start = useCallback(() => {
    socket.current?.close();
    seq.current = 0;
    dispatch({ type: "reset" });
    const s = new SessionSocket(
      defaultSocketUrl(),
      (msg) => dispatch({ type: "server", msg }),
      setStatus,
    );
    socket.current = s;
    s.connect(() => s.send({ type: "session_start", scene_id: sceneId }));
  }, [sceneId]);

  useEffect(() => {
    start();
    return () => socket.current?.close();
  }, [start]);

  const say = useCallback((text: string) => {
    seq.current += 1;
    socket.current?.send({ type: "text_utterance", seq: seq.current, text });
  }, []);

  const end = useCallback(() => socket.current?.send({ type: "session_end", reason: "user" }), []);

  return { state, status, say, end, restart: start };
}
