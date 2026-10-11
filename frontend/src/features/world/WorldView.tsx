import { useCallback, useEffect, useRef, useState } from "react";

import { drawMarker, drawPerson, renderMap } from "./draw";
import {
  AMBIENT,
  NPCS,
  PLAYER_LOOK,
  TALK_DISTANCE,
  TILE,
  COLS,
  ROWS,
  buildMap,
  type Ambient,
  type Dir,
  type NpcDef,
} from "./map";
import { ambientPosition, moveWithCollision, nearestInReach, type Vec } from "./physics";

const SPEED = 5; // tiles per second
const KEY_DIRS: Record<string, Dir> = {
  ArrowUp: "up",
  ArrowDown: "down",
  ArrowLeft: "left",
  ArrowRight: "right",
  w: "up",
  s: "down",
  a: "left",
  d: "right",
  W: "up",
  S: "down",
  A: "left",
  D: "right",
};

interface Props {
  cleared: ReadonlySet<string>;
  paused: boolean;
  onTalk: (npc: NpcDef) => void;
}

type Nearby = { kind: "npc"; npc: NpcDef } | { kind: "ambient"; who: Ambient } | null;

function isTyping(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/** The New York street: walk with arrows/WASD (or the on-screen pad), Space to talk. */
export function WorldView({ cleared, paused, onTalk }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pos = useRef<Vec>({ x: 22, y: 12.5 });
  const dir = useRef<Dir>("down");
  const held = useRef<Set<Dir>>(new Set());
  const walkTime = useRef(0);
  const nearbyRef = useRef<Nearby>(null);
  const [nearby, setNearby] = useState<Nearby>(null);
  const [toast, setToast] = useState<string | null>(null);
  const clearedRef = useRef(cleared);
  clearedRef.current = cleared;
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  const interact = useCallback(() => {
    const n = nearbyRef.current;
    if (!n || pausedRef.current) return;
    if (n.kind === "npc") onTalk(n.npc);
    else setToast(n.who.lineKo);
  }, [onTalk]);

  // keyboard
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (pausedRef.current || isTyping(e.target)) return;
      const d = KEY_DIRS[e.key];
      if (d) {
        held.current.add(d);
        e.preventDefault();
      } else if (e.key === " " || e.key === "Enter" || e.key === "e" || e.key === "E") {
        e.preventDefault();
        interact();
      }
    };
    const up = (e: KeyboardEvent) => {
      const d = KEY_DIRS[e.key];
      if (d) held.current.delete(d);
    };
    const clear = () => held.current.clear();
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", clear);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", clear);
    };
  }, [interact]);

  useEffect(() => {
    if (paused) held.current.clear();
  }, [paused]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  // game loop
  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const map = buildMap();
    const mapImage = renderMap(map);
    let frame = 0;
    let last = performance.now();

    const tick = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const t = now / 1000;

      // move
      let dx = 0;
      let dy = 0;
      if (!pausedRef.current) {
        for (const d of held.current) {
          if (d === "left") dx -= 1;
          if (d === "right") dx += 1;
          if (d === "up") dy -= 1;
          if (d === "down") dy += 1;
        }
      }
      const moving = dx !== 0 || dy !== 0;
      if (moving) {
        const len = Math.hypot(dx, dy);
        const blockers = [
          ...NPCS.map((n) => ({ x: n.x, y: n.y })),
          ...AMBIENT.map((a) => ambientPosition(a, t)),
        ];
        pos.current = moveWithCollision(
          map,
          pos.current,
          { x: (dx / len) * SPEED * dt, y: (dy / len) * SPEED * dt },
          blockers,
        );
        dir.current = Math.abs(dx) > Math.abs(dy) ? (dx < 0 ? "left" : "right") : dy < 0 ? "up" : "down";
        walkTime.current += dt;
      } else walkTime.current = 0;

      // who is close enough to talk to
      const ambients = AMBIENT.map((a) => ({ who: a, ...ambientPosition(a, t) }));
      const npc = nearestInReach(pos.current, NPCS, TALK_DISTANCE);
      const amb = npc ? null : nearestInReach(pos.current, ambients, TALK_DISTANCE);
      const next: Nearby = npc ? { kind: "npc", npc } : amb ? { kind: "ambient", who: amb.who } : null;
      const prev = nearbyRef.current;
      const same =
        prev?.kind === next?.kind &&
        (prev?.kind === "npc" ? prev.npc.id : prev?.who.id) === (next?.kind === "npc" ? next.npc.id : next?.who.id);
      if (!same) {
        nearbyRef.current = next;
        setNearby(next);
      }

      // draw
      const dpr = window.devicePixelRatio || 1;
      const W = Math.round(canvas.clientWidth * dpr);
      const H = Math.round(canvas.clientHeight * dpr);
      if (canvas.width !== W || canvas.height !== H) {
        canvas.width = W;
        canvas.height = H;
      }
      const p = Math.max(2, Math.floor(Math.min(W / (20 * TILE), H / (12 * TILE)) * 2) / 2);
      const viewW = W / p;
      const viewH = H / p;
      const camX = Math.max(0, Math.min(COLS * TILE - viewW, pos.current.x * TILE - viewW / 2));
      const camY = Math.max(0, Math.min(ROWS * TILE - viewH, pos.current.y * TILE - viewH / 2));
      ctx.imageSmoothingEnabled = false;
      ctx.fillStyle = "#0e1115";
      ctx.fillRect(0, 0, W, H);
      ctx.drawImage(mapImage, camX, camY, viewW, viewH, 0, 0, viewW * p, viewH * p);
      const screen = (v: Vec) => ({ x: (v.x * TILE - camX) * p, y: (v.y * TILE - camY) * p });

      const people: { y: number; draw: () => void }[] = [];
      for (const n of NPCS) {
        const s = screen(n);
        people.push({
          y: n.y,
          draw: () => {
            const near = nearbyRef.current?.kind === "npc" && nearbyRef.current.npc.id === n.id;
            const facing = near ? faceTowards(n, pos.current) : n.facing;
            drawPerson(ctx, s.x, s.y, p, n.look, facing, 0);
            drawMarker(ctx, s.x, s.y, p, clearedRef.current.has(n.sceneId), Math.sin(t * 3 + n.x) * 1.2);
          },
        });
      }
      for (const a of ambients) {
        const s = screen(a);
        const step = Math.floor(t * 6) % 2;
        people.push({ y: a.y, draw: () => drawPerson(ctx, s.x, s.y, p, a.who.look, a.dir, step) });
      }
      const me = screen(pos.current);
      const myStep = moving ? (Math.floor(walkTime.current * 8) % 2) + 1 : 0;
      people.push({ y: pos.current.y, draw: () => drawPerson(ctx, me.x, me.y, p, PLAYER_LOOK, dir.current, myStep) });
      people.sort((a, b) => a.y - b.y).forEach((x) => x.draw());

      // name tag over whoever is in reach
      const n = nearbyRef.current;
      if (n) {
        const who = n.kind === "npc" ? n.npc : ambients.find((a) => a.who.id === n.who.id);
        if (who) {
          const s = screen(who);
          const text = n.kind === "npc" ? `${n.npc.name} · ${n.npc.roleKo}` : "…";
          ctx.font = `${Math.round(4.5 * p)}px "Segoe UI", "Malgun Gothic", sans-serif`;
          const w = ctx.measureText(text).width + 4 * p;
          const top = s.y - 31 * p;
          ctx.fillStyle = "rgba(14,17,21,0.82)";
          ctx.fillRect(s.x - w / 2, top, w, 7 * p);
          ctx.fillStyle = "#fff";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(text, s.x, top + 3.6 * p);
        }
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, []);

  const hold = (d: Dir) => ({
    onPointerDown: (e: React.PointerEvent) => {
      e.preventDefault();
      held.current.add(d);
    },
    onPointerUp: () => held.current.delete(d),
    onPointerLeave: () => held.current.delete(d),
    onPointerCancel: () => held.current.delete(d),
  });

  return (
    <section className="world" aria-label="뉴욕 거리">
      <div className="world-stage">
        <canvas ref={canvasRef} className="world-canvas" role="img" aria-label="도트로 그린 뉴욕 거리. 방향키로 움직여요." />
        {nearby && (
          <div className="world-prompt" aria-live="polite">
            {nearby.kind === "npc" ? (
              <>
                <span>
                  <b>{nearby.npc.name}</b> ({nearby.npc.roleKo}) — {nearby.npc.teaserKo}
                </span>
                <button onClick={interact}>
                  대화하기 <kbd>Space</kbd>
                </button>
              </>
            ) : (
              <>
                <span>지나가는 사람이에요.</span>
                <button onClick={interact}>
                  말 걸기 <kbd>Space</kbd>
                </button>
              </>
            )}
          </div>
        )}
        {toast && <p className="world-toast">{toast}</p>}
      </div>
      <div className="dpad" aria-label="이동">
        <button className="dpad-up" aria-label="위로" {...hold("up")}>
          ▲
        </button>
        <button className="dpad-left" aria-label="왼쪽으로" {...hold("left")}>
          ◀
        </button>
        <button className="dpad-right" aria-label="오른쪽으로" {...hold("right")}>
          ▶
        </button>
        <button className="dpad-down" aria-label="아래로" {...hold("down")}>
          ▼
        </button>
      </div>
      <p className="muted world-help">
        방향키·WASD로 움직이고, 느낌표(!)가 떠 있는 사람에게 다가가 <kbd>Space</kbd>를 누르면 대화가 시작돼요.
      </p>
    </section>
  );
}

function faceTowards(from: Vec, to: Vec): Dir {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  if (Math.abs(dx) > Math.abs(dy)) return dx < 0 ? "left" : "right";
  return dy < 0 ? "up" : "down";
}
