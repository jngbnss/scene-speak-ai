import { existsSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  BLOCKS,
  LANES,
  PEOPLE,
  PLAYER_START,
  POND,
  PROPS,
  STREETS,
  TALK_DISTANCE,
  WORLD,
  buildBuildings,
  buildColliders,
  buildTrees,
  buildWalkers,
  inRect,
  moveCircle,
  onRoad,
  routeLength,
  routePoint,
  type Point,
  type Rect,
} from "../src/features/city/layout";
import { CRUISE, isGreen, stepCars, type Car } from "../src/features/city/traffic";

const SCENES = join(__dirname, "..", "..", "scenes");
const buildings = buildBuildings();
const trees = buildTrees();
const solids = buildColliders(buildings, trees);
const RADIUS = 0.35;

const blocked = (p: Point, rects: Rect[] = solids, r = RADIUS) =>
  rects.some((q) => p.x + r > q.x0 && p.x - r < q.x1 && p.z + r > q.z0 && p.z - r < q.z1);

/** 0.5 m cells the player can reach on foot from the start. */
function reachable(): Set<string> {
  const key = (x: number, z: number) => `${x},${z}`;
  const seen = new Set<string>();
  const start = [Math.round(PLAYER_START.x * 2), Math.round(PLAYER_START.z * 2)];
  const queue = [start];
  while (queue.length) {
    const [x, z] = queue.pop()!;
    const k = key(x, z);
    if (seen.has(k)) continue;
    const p = { x: x / 2, z: z / 2 };
    if (!inRect(p, WORLD) || blocked(p)) continue;
    seen.add(k);
    queue.push([x + 1, z], [x - 1, z], [x, z + 1], [x, z - 1]);
  }
  return seen;
}

function samples(route: Point[], step = 0.5): Point[] {
  const out: Point[] = [];
  for (let d = 0; d < routeLength(route); d += step) out.push(routePoint(route, d));
  return out;
}

describe("3D New York layout", () => {
  it("starts the player on a free sidewalk", () => {
    expect(blocked(PLAYER_START)).toBe(false);
    expect(onRoad(PLAYER_START)).toBe(false);
  });

  it("gives every person a unique id and a scene file on the server", () => {
    expect(new Set(PEOPLE.map((p) => p.id)).size).toBe(PEOPLE.length);
    expect(new Set(PEOPLE.map((p) => p.sceneId)).size).toBe(PEOPLE.length);
    for (const p of PEOPLE) {
      const dirs = p.kind === "chat" ? ["people"] : ["talks", "."];
      const found = dirs.some((d) => existsSync(join(SCENES, d, `${p.sceneId}.yaml`)));
      expect(found, p.sceneId).toBe(true);
      expect(Boolean(p.spot) !== Boolean(p.route), p.id).toBe(true);
    }
    expect(PEOPLE.filter((p) => p.kind === "mission")).toHaveLength(5);
    expect(PEOPLE.filter((p) => p.kind === "chat").length).toBeGreaterThanOrEqual(10);
  });

  it("puts nobody inside a building, a tree or the pond", () => {
    const hard = [...buildings, POND, ...trees.map((t) => ({ x0: t.x - 0.5, x1: t.x + 0.5, z0: t.z - 0.5, z1: t.z + 0.5 }))];
    for (const p of PEOPLE) {
      for (const pt of p.spot ? [p.spot] : samples(p.route!)) {
        expect(blocked(pt, hard, 0.25), `${p.id} at ${pt.x},${pt.z}`).toBe(false);
        expect(onRoad(pt), `${p.id} on the road at ${pt.x},${pt.z}`).toBe(false);
      }
    }
  });

  it("keeps background walkers on sidewalks and plazas", () => {
    const hard = [...buildings, POND];
    for (const w of buildWalkers()) {
      for (const pt of samples(w.route)) {
        expect(blocked(pt, hard, 0.25), `${w.id} at ${pt.x},${pt.z}`).toBe(false);
        expect(inRect(pt, WORLD), `${w.id} outside the map`).toBe(true);
        expect(onRoad(pt), `${w.id} on the road`).toBe(false);
      }
    }
  });

  it("lets the player walk up to everyone", () => {
    const cells = [...reachable()].map((k) => {
      const [x, z] = k.split(",").map(Number);
      return { x: x / 2, z: z / 2 };
    });
    expect(cells.length).toBeGreaterThan(5000);
    for (const p of PEOPLE) {
      const spots = p.spot ? [p.spot] : samples(p.route!, 5);
      for (const s of spots) {
        const close = cells.some((c) => Math.hypot(c.x - s.x, c.z - s.z) < TALK_DISTANCE - 0.2);
        expect(close, `${p.id} at ${s.x},${s.z}`).toBe(true);
      }
    }
  });

  it("keeps street furniture off the roads", () => {
    for (const p of PROPS) expect(onRoad(p), `${p.kind} at ${p.x},${p.z}`).toBe(false);
  });

  it("splits the city blocks into buildings that do not overlap", () => {
    expect(BLOCKS).toHaveLength(3);
    for (let i = 0; i < buildings.length; i++) {
      for (let j = i + 1; j < buildings.length; j++) {
        const a = buildings[i];
        const b = buildings[j];
        const overlap = Math.min(a.x1, b.x1) - Math.max(a.x0, b.x0) > 0.01 && Math.min(a.z1, b.z1) - Math.max(a.z0, b.z0) > 0.01;
        expect(overlap, `${i} and ${j}`).toBe(false);
      }
    }
  });
});

describe("movement", () => {
  it("slides along a wall instead of passing through", () => {
    const wall = [{ x0: 1, x1: 2, z0: -5, z1: 5 }];
    const p = moveCircle({ x: 0, z: 0 }, 2, 1, 0.35, wall);
    expect(p.x).toBe(0);
    expect(p.z).toBe(1);
  });

  it("walks a closed route and wraps around", () => {
    const square = [
      { x: 0, z: 0 },
      { x: 10, z: 0 },
      { x: 10, z: 10 },
      { x: 0, z: 10 },
    ];
    expect(routeLength(square)).toBe(40);
    expect(routePoint(square, 15)).toMatchObject({ x: 10, z: 5 });
    expect(routePoint(square, 45)).toMatchObject({ x: 5, z: 0 });
    expect(routePoint(square, 5).heading).toBeCloseTo(Math.PI / 2);
  });
});

describe("traffic", () => {
  const avenueLane = LANES.findIndex((l) => l.axis === "z" && l.dir === 1);
  const street = STREETS[1].z;

  it("never shows green both ways", () => {
    for (let t = 0; t < 60; t += 0.25) expect(isGreen("x", t) && isGreen("z", t)).toBe(false);
  });

  it("stops at a red light and goes on green", () => {
    const car: Car = { lane: avenueLane, s: street - 40, speed: CRUISE, color: "#f7c513" };
    let t = 13; // all red, then streets green: avenues wait
    for (let i = 0; i < 1000 && t < 27; i++, t += 0.025) stepCars([car], 0.025, t, null);
    expect(car.speed).toBeCloseTo(0, 1);
    expect(car.s).toBeLessThan(street - 6);
    for (let i = 0; i < 240; i++, t += 0.025) stepCars([car], 0.025, t, null);
    expect(car.s).toBeGreaterThan(street + 6);
  });

  it("stops for the player standing in the lane", () => {
    const lane = LANES[avenueLane];
    const car: Car = { lane: avenueLane, s: 60, speed: CRUISE, color: "#f7c513" };
    const player = { x: lane.at, z: 75 };
    for (let i = 0; i < 300; i++) stepCars([car], 0.025, 2, player);
    expect(car.speed).toBeCloseTo(0, 1);
    expect(car.s).toBeLessThan(player.z - 2);
  });

  it("keeps a gap to the car ahead", () => {
    const lane = LANES[avenueLane];
    const a: Car = { lane: avenueLane, s: 70, speed: 0, color: "#f7c513" };
    const b: Car = { lane: avenueLane, s: 40, speed: CRUISE, color: "#f7c513" };
    // The player stands in the lane just ahead of car a, so a cannot move.
    for (let i = 0; i < 400; i++) stepCars([a, b], 0.025, 2, { x: lane.at, z: 74 });
    expect(b.speed).toBeCloseTo(0, 1);
    expect(a.s - b.s).toBeGreaterThan(6);
  });
});
