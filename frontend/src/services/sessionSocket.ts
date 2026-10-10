import type { ClientMessage, ServerMessage } from "../types/messages";

export type SocketStatus = "connecting" | "open" | "closed";

export function defaultSocketUrl(): string {
  const configured = import.meta.env.VITE_WS_URL as string | undefined;
  if (configured) return configured;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/session`;
}

export class SessionSocket {
  private ws: WebSocket | null = null;

  constructor(
    private readonly url: string,
    private readonly onMessage: (msg: ServerMessage) => void,
    private readonly onStatus: (status: SocketStatus) => void,
  ) {}

  connect(onOpen?: () => void): void {
    this.onStatus("connecting");
    const ws = new WebSocket(this.url);
    this.ws = ws;
    ws.onopen = () => {
      this.onStatus("open");
      onOpen?.();
    };
    ws.onclose = () => {
      if (this.ws === ws) this.onStatus("closed");
    };
    ws.onmessage = (event) => {
      try {
        this.onMessage(JSON.parse(event.data as string) as ServerMessage);
      } catch {
        console.error("Unreadable server message", event.data);
      }
    };
  }

  send(msg: ClientMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(msg));
  }

  close(): void {
    const ws = this.ws;
    this.ws = null;
    ws?.close();
  }
}
