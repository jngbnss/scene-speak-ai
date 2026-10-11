import { isSolid, type Ambient, type Dir, type TileMap } from "./map";

export interface Vec {
  x: number;
  y: number;
}

// The player's feet box, in tiles, relative to the feet point.
const HALF_W = 0.3;
const TOP = 0.35;
const PERSON_RADIUS = 0.6;

function boxFree(map: TileMap, p: Vec): boolean {
  const xs = [p.x - HALF_W, p.x + HALF_W];
  const ys = [p.y - TOP, p.y - 0.02];
  return xs.every((x) => ys.every((y) => !isSolid(map, x, y)));
}

function clearOfPeople(from: Vec, to: Vec, people: Vec[]): boolean {
  // Moving away from someone you already overlap is always allowed, so nobody gets stuck.
  return people.every((o) => {
    const after = Math.hypot(to.x - o.x, to.y - o.y);
    return after >= PERSON_RADIUS || after > Math.hypot(from.x - o.x, from.y - o.y);
  });
}

/** Moves along x and y separately so the player slides along walls. */
export function moveWithCollision(map: TileMap, pos: Vec, delta: Vec, people: Vec[] = []): Vec {
  let next = { ...pos };
  const tryX = { x: next.x + delta.x, y: next.y };
  if (boxFree(map, tryX) && clearOfPeople(next, tryX, people)) next = tryX;
  const tryY = { x: next.x, y: next.y + delta.y };
  if (boxFree(map, tryY) && clearOfPeople(next, tryY, people)) next = tryY;
  return next;
}

export function nearestInReach<T extends Vec>(pos: Vec, items: T[], reach: number): T | null {
  let best: T | null = null;
  let bestDist = reach;
  for (const item of items) {
    const d = Math.hypot(item.x - pos.x, item.y - pos.y);
    if (d <= bestDist) {
      best = item;
      bestDist = d;
    }
  }
  return best;
}

// How far (tiles) and how fast each passer-by walks back and forth.
const WANDER: Record<string, { range: number; speed: number }> = {
  jogger: { range: 7, speed: 0.45 },
  businessman: { range: 3, speed: 0.5 },
};

/** Passers-by pace back and forth along x; the rest stand still. */
export function ambientPosition(a: Ambient, t: number): Vec & { dir: Dir } {
  const w = WANDER[a.id];
  if (!w) return { x: a.x, y: a.y, dir: a.facing };
  const x = a.x + Math.sin(t * w.speed) * w.range;
  const dir: Dir = Math.cos(t * w.speed) >= 0 ? "right" : "left";
  return { x, y: a.y, dir };
}
