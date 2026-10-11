import { useCallback, useEffect, useRef, useState } from "react";

import type { City } from "./city";
import type { Person } from "./layout";

interface Props {
  cleared: ReadonlySet<string>;
  paused: boolean;
  onTalk: (person: Person) => void;
}

const MOVE_KEYS: Record<string, [number, number]> = {
  ArrowUp: [1, 0],
  KeyW: [1, 0],
  ArrowDown: [-1, 0],
  KeyS: [-1, 0],
  ArrowLeft: [0, -1],
  KeyA: [0, -1],
  ArrowRight: [0, 1],
  KeyD: [0, 1],
};

function isTyping(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

/** The 3D street: WASD/arrows to walk, drag to look around, Space to talk. */
export function CityView({ cleared, paused, onTalk }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const labelRef = useRef<HTMLDivElement>(null);
  const cityRef = useRef<City | null>(null);
  const keys = useRef<Set<string>>(new Set());
  const stick = useRef({ forward: 0, strafe: 0 });
  const [nearby, setNearby] = useState<Person | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const syncInput = useCallback(() => {
    const city = cityRef.current;
    if (!city) return;
    let forward = stick.current.forward;
    let strafe = stick.current.strafe;
    for (const k of keys.current) {
      const m = MOVE_KEYS[k];
      if (m) {
        forward += m[0];
        strafe += m[1];
      }
    }
    city.input = {
      forward: Math.max(-1, Math.min(1, forward)),
      strafe: Math.max(-1, Math.min(1, strafe)),
      run: keys.current.has("ShiftLeft") || keys.current.has("ShiftRight"),
      turn: (keys.current.has("KeyE") ? 1 : 0) - (keys.current.has("KeyQ") ? 1 : 0),
    };
  }, []);

  const talk = useCallback(() => {
    const target = cityRef.current?.target;
    if (target) onTalk(target);
  }, [onTalk]);

  // Build the city once (three.js is loaded on demand so the first page stays small).
  useEffect(() => {
    let disposed = false;
    let observer: ResizeObserver | null = null;
    import("./city")
      .then(({ City }) => {
        const canvas = canvasRef.current;
        if (disposed || !canvas) return;
        try {
          const city = new City(canvas, labelRef.current, { onNearby: setNearby });
          cityRef.current = city;
          observer = new ResizeObserver(() => city.resize());
          observer.observe(canvas);
          setLoading(false);
        } catch (e) {
          setError(e instanceof Error ? e.message : String(e));
        }
      })
      .catch((e: unknown) => setError(String(e)));
    return () => {
      disposed = true;
      observer?.disconnect();
      cityRef.current?.dispose();
      cityRef.current = null;
    };
  }, []);

  useEffect(() => {
    cityRef.current?.setCleared(cleared);
  }, [cleared, loading]);

  useEffect(() => {
    const city = cityRef.current;
    if (!city) return;
    if (paused) {
      keys.current.clear();
      city.stop();
    } else {
      city.resize();
      city.start();
    }
  }, [paused, loading]);

  // Keyboard
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (paused || isTyping(e.target)) return;
      if (e.code === "Space" || e.code === "Enter" || e.code === "KeyF") {
        e.preventDefault();
        if (!e.repeat) talk();
        return;
      }
      if (MOVE_KEYS[e.code] || e.code.startsWith("Shift") || e.code === "KeyQ" || e.code === "KeyE") {
        if (e.code.startsWith("Arrow")) e.preventDefault();
        keys.current.add(e.code);
        syncInput();
      }
    };
    const up = (e: KeyboardEvent) => {
      keys.current.delete(e.code);
      syncInput();
    };
    const clear = () => {
      keys.current.clear();
      syncInput();
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", clear);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", clear);
    };
  }, [paused, talk, syncInput]);

  // On-screen joystick for touch screens
  const stickBase = useRef<HTMLDivElement>(null);
  const [knob, setKnob] = useState({ x: 0, y: 0 });
  const stickPointer = useRef<number | null>(null);
  const moveStick = (e: React.PointerEvent) => {
    const base = stickBase.current?.getBoundingClientRect();
    if (!base) return;
    const r = base.width / 2;
    let x = (e.clientX - base.left - r) / r;
    let y = (e.clientY - base.top - r) / r;
    const len = Math.hypot(x, y);
    if (len > 1) {
      x /= len;
      y /= len;
    }
    setKnob({ x, y });
    stick.current = { forward: -y, strafe: x };
    syncInput();
  };
  const releaseStick = () => {
    stickPointer.current = null;
    setKnob({ x: 0, y: 0 });
    stick.current = { forward: 0, strafe: 0 };
    syncInput();
  };

  return (
    <section className="world" aria-label="뉴욕 거리 (3D)">
      <div className="world-stage">
        <canvas ref={canvasRef} className="world-canvas city-canvas" role="img" aria-label="3D로 만든 뉴욕 거리. WASD로 걷고 드래그로 둘러봐요." />
        <div ref={labelRef} className="city-label" hidden />
        {loading && !error && <p className="city-loading">뉴욕 거리를 만드는 중…</p>}
        {error && (
          <p className="banner error city-error">
            3D 화면을 열 수 없어요. 브라우저의 하드웨어 가속(WebGL)이 켜져 있는지 확인해 주세요. ({error})
          </p>
        )}
        {nearby && (
          <div className="world-prompt" aria-live="polite">
            <span>
              <b>{nearby.name}</b> ({nearby.roleKo}) — {nearby.teaserKo}
            </span>
            <button onClick={talk}>
              {nearby.kind === "mission" ? "대화하기" : "말 걸기"} <kbd>Space</kbd>
            </button>
          </div>
        )}
        <div
          ref={stickBase}
          className="stick"
          aria-label="이동 조이스틱"
          onPointerDown={(e) => {
            stickPointer.current = e.pointerId;
            e.currentTarget.setPointerCapture(e.pointerId);
            moveStick(e);
          }}
          onPointerMove={(e) => stickPointer.current === e.pointerId && moveStick(e)}
          onPointerUp={releaseStick}
          onPointerCancel={releaseStick}
        >
          <span className="stick-knob" style={{ transform: `translate(${knob.x * 28}px, ${knob.y * 28}px)` }} />
        </div>
      </div>
      <p className="muted world-help">
        <kbd>W</kbd>
        <kbd>A</kbd>
        <kbd>S</kbd>
        <kbd>D</kbd> 걷기 · <kbd>Shift</kbd> 달리기 · 마우스 드래그(또는 <kbd>Q</kbd>
        <kbd>E</kbd>)로 둘러보기 · 휠로 확대. 느낌표(!)는 미션, 말풍선은 수다를 떨 수 있는 사람이에요. 가까이 가서{" "}
        <kbd>Space</kbd>를 누르세요.
      </p>
    </section>
  );
}
