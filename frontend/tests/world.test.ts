import { describe, expect, it } from "vitest";

import { AMBIENT, COLS, NPCS, PLAYER_START, ROWS, TALK_DISTANCE, buildMap, isSolid } from "../src/features/world/map";
import { ambientPosition, moveWithCollision, nearestInReach } from "../src/features/world/physics";

const map = buildMap();

/** Tiles reachable on foot from the start (4-neighbour flood fill). */
function reachable(): Set<string> {
  const seen = new Set<string>();
  const queue = [[Math.floor(PLAYER_START.x), Math.floor(PLAYER_START.y)]];
  while (queue.length) {
    const [x, y] = queue.pop()!;
    const key = `${x},${y}`;
    if (seen.has(key) || isSolid(map, x + 0.5, y + 0.5)) continue;
    seen.add(key);
    queue.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1]);
  }
  return seen;
}

describe("New York map", () => {
  it("has the declared size", () => {
    expect(map).toHaveLength(ROWS);
    expect(map.every((row) => row.length === COLS)).toBe(true);
  });

  it("starts the player on open ground", () => {
    expect(isSolid(map, PLAYER_START.x, PLAYER_START.y - 0.1)).toBe(false);
  });

  it("lets the player walk up to every NPC", () => {
    const open = reachable();
    for (const npc of NPCS) {
      expect(isSolid(map, npc.x, npc.y - 0.1), npc.id).toBe(false);
      // some open tile within talking distance of the NPC
      const near = [...open].some((key) => {
        const [x, y] = key.split(",").map(Number);
        return Math.hypot(x + 0.5 - npc.x, y + 0.5 - npc.y) <= TALK_DISTANCE;
      });
      expect(near, npc.id).toBe(true);
    }
  });

  it("gives every NPC its own scene and a unique id", () => {
    expect(new Set(NPCS.map((n) => n.sceneId)).size).toBe(NPCS.length);
    expect(new Set(NPCS.map((n) => n.id)).size).toBe(NPCS.length);
  });

  it("keeps passers-by on open ground while they walk", () => {
    for (const a of AMBIENT) {
      for (let t = 0; t < 20; t += 0.5) {
        const p = ambientPosition(a, t);
        expect(isSolid(map, p.x, p.y - 0.1), `${a.id} at t=${t}`).toBe(false);
      }
    }
  });
});

describe("movement", () => {
  it("stops at buildings but slides along them", () => {
    // Just below the hotel (rows 13-18), moving up-right: up is blocked, right is free.
    const start = { x: 5.5, y: 19.5 };
    const next = moveWithCollision(map, start, { x: 0.2, y: -0.5 });
    expect(next.x).toBeCloseTo(5.7);
    expect(next.y).toBe(19.5);
  });

  it("does not walk through people but can step away from them", () => {
    const npc = { x: 10, y: 20 };
    const towards = moveWithCollision(map, { x: 9.5, y: 20 }, { x: 0.3, y: 0 }, [npc]);
    expect(towards.x).toBe(9.5);
    const away = moveWithCollision(map, { x: 9.7, y: 20 }, { x: -0.3, y: 0 }, [npc]);
    expect(away.x).toBeCloseTo(9.4);
  });

  it("finds the closest NPC within reach", () => {
    const officer = NPCS.find((n) => n.id === "officer")!;
    expect(nearestInReach({ x: officer.x, y: officer.y - 1 }, NPCS, TALK_DISTANCE)?.id).toBe("officer");
    expect(nearestInReach({ x: officer.x, y: officer.y - 5 }, NPCS, TALK_DISTANCE)).toBeNull();
  });
});
