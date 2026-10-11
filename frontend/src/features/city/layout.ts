/**
 * The 3D New York layout as plain data (no three.js here, so it is easy to test).
 * Units are meters. x grows east, z grows south: Central Park is at negative z.
 * Avenues run north-south, streets east-west, like Midtown Manhattan.
 */

export interface Rect {
  x0: number;
  z0: number;
  x1: number;
  z1: number;
}

export interface Look {
  skin: string;
  hair: string;
  shirt: string;
  pants: string;
  shoes?: string;
  hat?: string;
  apron?: string;
  vest?: string;
  /** Long hair falls behind the head. */
  longHair?: boolean;
  /** 0.9-1.1, scales the whole body. */
  height?: number;
}

export interface Point {
  x: number;
  z: number;
}

export type TalkKind = "mission" | "chat";

/** Anyone you can walk up to and talk to. */
export interface Person {
  id: string;
  /** Backend scene id: scenes/*.yaml, scenes/talks/*.yaml or scenes/people/*.yaml. */
  sceneId: string;
  kind: TalkKind;
  name: string;
  roleKo: string;
  /** One line shown when the player walks up. */
  teaserKo: string;
  /** Example line shown in the empty input box. */
  exampleEn: string;
  look: Look;
  /** Where they stand (or sit), or the loop they walk (closed polygon). */
  spot?: Point & { facing: number; sit?: boolean };
  route?: Point[];
  speed?: number;
  /** Where on the route they start, 0-1. */
  offset?: number;
}

// ----- streets ---------------------------------------------------------------------------

export const WORLD: Rect = { x0: -105, z0: -130, x1: 105, z1: 85 };
export const ROAD_HALF = 6;
export const SIDEWALK = 4;
const INSET = ROAD_HALF + SIDEWALK;

export const AVENUES = [
  { x: -70, name: "7th Ave" },
  { x: 0, name: "6th Ave" },
  { x: 70, name: "5th Ave" },
];
export const STREETS = [
  { z: -45, name: "59th St" },
  { z: 5, name: "52nd St" },
  { z: 55, name: "45th St" },
];

/** South edge of Central Park's grass (the park sidewalk is between it and 59th St). */
export const PARK_EDGE = STREETS[0].z - INSET;

const XS = [WORLD.x0, ...AVENUES.map((a) => a.x), WORLD.x1];
const ZS = [STREETS[0].z, STREETS[1].z, STREETS[2].z, WORLD.z1];

/**
 * City blocks south of the park, inside their sidewalks. blocks[row][col], row 0 = north.
 * Blocks at the map's edge keep a sidewalk along the edge too.
 */
export const BLOCKS: Rect[][] = ZS.slice(0, -1).map((z0, r) =>
  XS.slice(0, -1).map((x0, c) => ({
    x0: x0 === WORLD.x0 ? x0 + SIDEWALK : x0 + INSET,
    x1: XS[c + 1] === WORLD.x1 ? XS[c + 1] - SIDEWALK : XS[c + 1] - INSET,
    z0: z0 + INSET,
    z1: ZS[r + 1] === WORLD.z1 ? ZS[r + 1] - SIDEWALK : ZS[r + 1] - INSET,
  })),
);

export function onRoad(p: Point): boolean {
  return (
    AVENUES.some((a) => Math.abs(p.x - a.x) < ROAD_HALF && p.z > STREETS[0].z - ROAD_HALF) ||
    STREETS.some((s) => Math.abs(p.z - s.z) < ROAD_HALF)
  );
}

// ----- buildings and landmarks ------------------------------------------------------------

export type BuildingStyle = "brick" | "glass" | "stone" | "hotel" | "cafe" | "station" | "tower";

export interface Building extends Rect {
  height: number;
  style: BuildingStyle;
  color: string;
  /** Text on a sign over the door, facing the given side. */
  sign?: { text: string; side: "n" | "s" | "e" | "w"; color: string };
}

export interface Billboard {
  x: number;
  z: number;
  y: number;
  w: number;
  h: number;
  /** Rotation around y (radians); 0 faces south. */
  rot: number;
  lines: string[];
  bg: string;
  fg: string;
}

const PALETTE = ["#b5654a", "#8f5b46", "#c8b89a", "#9aa3ad", "#6f7d8c", "#d8cfc0", "#a0523d", "#7b8a7a"];

function rand(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}

/** Split a block into buildings along its longer side. */
function fillBlock(b: Rect, seed: number, skip: Rect[] = []): Building[] {
  const r = rand(seed);
  const out: Building[] = [];
  const alongX = b.x1 - b.x0 >= b.z1 - b.z0;
  const length = alongX ? b.x1 - b.x0 : b.z1 - b.z0;
  let pos = 0;
  while (pos < length - 0.5) {
    const w = Math.min(length - pos, 10 + Math.floor(r() * 12));
    const piece: Rect = alongX
      ? { x0: b.x0 + pos, x1: b.x0 + pos + w, z0: b.z0, z1: b.z1 }
      : { x0: b.x0, x1: b.x1, z0: b.z0 + pos, z1: b.z0 + pos + w };
    pos += w;
    const parts = subtract(piece, skip);
    for (const part of parts) {
      const tall = r() < 0.25;
      out.push({
        ...part,
        height: tall ? 45 + r() * 40 : 14 + r() * 22,
        style: tall ? (r() < 0.5 ? "glass" : "tower") : r() < 0.6 ? "brick" : "stone",
        color: PALETTE[Math.floor(r() * PALETTE.length)],
      });
    }
  }
  return out;
}

/** a minus the rectangles in cut (only cuts that span a's full depth or width are needed here). */
function subtract(a: Rect, cuts: Rect[]): Rect[] {
  let parts = [a];
  for (const c of cuts) {
    const next: Rect[] = [];
    for (const p of parts) {
      if (c.x1 <= p.x0 || c.x0 >= p.x1 || c.z1 <= p.z0 || c.z0 >= p.z1) {
        next.push(p);
        continue;
      }
      if (c.x0 > p.x0) next.push({ ...p, x1: c.x0 });
      if (c.x1 < p.x1) next.push({ ...p, x0: c.x1 });
      const mx0 = Math.max(p.x0, c.x0);
      const mx1 = Math.min(p.x1, c.x1);
      if (c.z0 > p.z0) next.push({ x0: mx0, x1: mx1, z0: p.z0, z1: c.z0 });
      if (c.z1 < p.z1) next.push({ x0: mx0, x1: mx1, z0: c.z1, z1: p.z1 });
    }
    parts = next.filter((p) => p.x1 - p.x0 > 1 && p.z1 - p.z0 > 1);
  }
  return parts;
}

// Named blocks
const B = BLOCKS;
/** Times Square: an open plaza where 7th Ave meets Broadway. */
export const TIMES_SQUARE: Rect = B[1][1];
const CAFE: Building = {
  x0: 22,
  x1: 40,
  z0: B[1][2].z0,
  z1: B[1][2].z0 + 14,
  height: 12,
  style: "cafe",
  color: "#f1e6d2",
  sign: { text: "CAFE", side: "n", color: "#1f7a4d" },
};
const HOTEL: Building = {
  ...B[1][0],
  height: 70,
  style: "hotel",
  color: "#c9b48f",
  sign: { text: "HOTEL", side: "e", color: "#7a1f2e" },
};
const STATION: Building = {
  x0: B[2][1].x0 + 4,
  x1: B[2][1].x1 - 4,
  z0: B[2][1].z0,
  z1: B[2][1].z1,
  height: 22,
  style: "station",
  color: "#d8cdb4",
  sign: { text: "GRAND CENTRAL", side: "n", color: "#2b3a4c" },
};

export function buildBuildings(): Building[] {
  const out: Building[] = [HOTEL, CAFE, STATION];
  B.forEach((row, r) =>
    row.forEach((block, c) => {
      if (block === TIMES_SQUARE || (r === 1 && c === 0)) return; // the plaza, the hotel
      if (r === 2 && c === 1) {
        out.push(...fillBlock({ ...block, x1: STATION.x0 }, 7), ...fillBlock({ ...block, x0: STATION.x1 }, 8));
        return;
      }
      const skip = r === 1 && c === 2 ? [CAFE] : [];
      out.push(...fillBlock(block, 100 + r * 10 + c, skip));
    }),
  );
  // Times Square: towers on its corners carry the big billboards
  const t = TIMES_SQUARE;
  out.push(
    { x0: t.x0, x1: t.x0 + 12, z0: t.z0, z1: t.z0 + 10, height: 60, style: "tower", color: "#3b4250" },
    { x0: t.x1 - 12, x1: t.x1, z0: t.z0, z1: t.z0 + 10, height: 55, style: "tower", color: "#40394a" },
    { x0: t.x0, x1: t.x0 + 10, z0: t.z1 - 8, z1: t.z1, height: 48, style: "tower", color: "#2f3a45" },
    { x0: t.x1 - 10, x1: t.x1, z0: t.z1 - 8, z1: t.z1, height: 50, style: "tower", color: "#463a3a" },
  );
  return out;
}

export function buildBillboards(): Billboard[] {
  const t = TIMES_SQUARE;
  return [
    { x: t.x0 + 6, z: t.z0 + 10.05, y: 16, w: 11, h: 14, rot: 0, lines: ["NEW", "YORK"], bg: "#d6264f", fg: "#fff" },
    { x: t.x1 - 6, z: t.z0 + 10.05, y: 18, w: 11, h: 16, rot: 0, lines: ["SPEAK", "UP!"], bg: "#1c4fd8", fg: "#ffe14d" },
    { x: t.x0 + 5, z: t.z1 - 8.05, y: 14, w: 9, h: 12, rot: Math.PI, lines: ["BROAD", "WAY"], bg: "#ffcc33", fg: "#14181e" },
    { x: t.x1 - 5, z: t.z1 - 8.05, y: 15, w: 9, h: 12, rot: Math.PI, lines: ["I ♥", "NYC"], bg: "#ffffff", fg: "#d6264f" },
    { x: t.x0 + 12.05, z: t.z0 + 5, y: 22, w: 9, h: 10, rot: Math.PI / 2, lines: ["SHOW", "8 PM"], bg: "#7b2ff2", fg: "#fff" },
    { x: t.x1 - 12.05, z: t.z0 + 5, y: 20, w: 9, h: 10, rot: -Math.PI / 2, lines: ["HELLO", "WORLD"], bg: "#0f9d76", fg: "#fff" },
  ];
}

// ----- park -------------------------------------------------------------------------------

export const POND: Rect = { x0: 30, z0: -110, x1: 70, z1: -85 };
export const PARK_PATHS: Rect[] = [
  { x0: WORLD.x0, x1: WORLD.x1, z0: -82, z1: -78 }, // east-west path
  { x0: -42, x1: -38, z0: WORLD.z0, z1: PARK_EDGE }, // north-south paths
  { x0: 13, x1: 17, z0: WORLD.z0, z1: PARK_EDGE },
  { x0: -42, x1: 17, z0: -122, z1: -118 }, // the jogging loop
];

export function buildTrees(): Point[] {
  const r = rand(42);
  const trees: Point[] = [];
  let tries = 0;
  while (trees.length < 70 && tries++ < 2000) {
    const p = { x: WORLD.x0 + 4 + r() * (WORLD.x1 - WORLD.x0 - 8), z: WORLD.z0 + 4 + r() * (PARK_EDGE - WORLD.z0 - 7) };
    if (inRect(p, grow(POND, 3)) || PARK_PATHS.some((q) => inRect(p, grow(q, 2.5)))) continue;
    if (trees.some((t) => Math.hypot(t.x - p.x, t.z - p.z) < 6)) continue;
    if ([...PEOPLE_SPOTS(), ...PROPS].some((s) => Math.hypot(s.x - p.x, s.z - p.z) < 4)) continue;
    trees.push(p);
  }
  return trees;
}

// ----- street furniture -------------------------------------------------------------------

export interface Prop {
  kind: "cart" | "bench" | "lamp" | "subway" | "hydrant" | "easel";
  x: number;
  z: number;
  /** Rotation around y; 0 means the front faces south (+z). */
  rot: number;
}

const cafeFront = CAFE.z0 - 2; // middle of the sidewalk in front of the café
export const PROPS: Prop[] = [
  { kind: "cart", x: 52, z: cafeFront, rot: 0 },
  { kind: "subway", x: -22, z: B[1][1].z1 + 2, rot: 0 },
  { kind: "bench", x: -62.6, z: 30, rot: Math.PI / 2 },
  { kind: "bench", x: 48, z: B[1][2].z1 + 0.9, rot: 0 },
  { kind: "bench", x: -20, z: -90, rot: 0 },
  { kind: "bench", x: 2, z: -76, rot: Math.PI },
  { kind: "easel", x: -10, z: PARK_EDGE - 3, rot: Math.PI },
  { kind: "hydrant", x: -7.5, z: -8, rot: 0 },
  { kind: "hydrant", x: 62.5, z: 47.5, rot: 0 },
  ...AVENUES.flatMap((a) =>
    [-25, 25, 75].flatMap((z) => [
      { kind: "lamp" as const, x: a.x - ROAD_HALF - 0.6, z, rot: 0 },
      { kind: "lamp" as const, x: a.x + ROAD_HALF + 0.6, z: z - 10, rot: Math.PI },
    ]),
  ),
];

const PROP_SIZE: Record<Prop["kind"], [number, number]> = {
  cart: [2.4, 1.4],
  bench: [2, 0.7],
  lamp: [0.4, 0.4],
  subway: [3.4, 2.4],
  hydrant: [0.5, 0.5],
  easel: [1, 0.8],
};

// ----- people -----------------------------------------------------------------------------

const SKIN = ["#f1c7a5", "#e0ac84", "#c68a5e", "#9a6440", "#6e4428"];

/** A loop on the sidewalk around a block, `d` meters out from its edge. */
export function aroundBlock(b: Rect, d = 2, clockwise = true): Point[] {
  const pts = [
    { x: b.x0 - d, z: b.z0 - d },
    { x: b.x1 + d, z: b.z0 - d },
    { x: b.x1 + d, z: b.z1 + d },
    { x: b.x0 - d, z: b.z1 + d },
  ];
  return clockwise ? pts : pts.reverse();
}

const PARK_LOOP: Point[] = [
  { x: -40, z: -80 },
  { x: 15, z: -80 },
  { x: 15, z: -120 },
  { x: -40, z: -120 },
];

/** A loop inside the Times Square plaza, clear of the corner towers. */
export const PLAZA_LOOP: Point[] = [
  { x: -48, z: 26 },
  { x: -22, z: 26 },
  { x: -22, z: 36 },
  { x: -48, z: 36 },
];

/** On the sidewalk north of Times Square, looking at the officer. */
export const PLAYER_START = { x: -35, z: 13, facing: 0 };

export const PEOPLE: Person[] = [
  // Missions (D-030)
  {
    id: "barista",
    sceneId: "new-york-cafe",
    kind: "mission",
    name: "Maya",
    roleKo: "카페 바리스타",
    teaserKo: "카페 앞에서 주문을 받고 있어요.",
    exampleEn: "Can I get a large hot latte?",
    look: { skin: SKIN[1], hair: "#3b2416", shirt: "#ffffff", pants: "#30343c", apron: "#1f7a4d", longHair: true },
    spot: { x: 31, z: cafeFront, facing: Math.PI },
  },
  {
    id: "vendor",
    sceneId: "hot-dog-stand",
    kind: "mission",
    name: "Tony",
    roleKo: "핫도그 노점상",
    teaserKo: "고소한 냄새가 나요. 점심으로 어때요?",
    exampleEn: "Can I get a hot dog, please?",
    look: { skin: SKIN[0], hair: "#5a3a22", shirt: "#d23a2e", pants: "#30343c", hat: "#d23a2e", apron: "#f4f4f4", height: 1.05 },
    spot: { x: 52, z: cafeFront + 1.2, facing: Math.PI },
  },
  {
    id: "officer",
    sceneId: "times-square-directions",
    kind: "mission",
    name: "Officer Davis",
    roleKo: "경찰관",
    teaserKo: "센트럴 파크에 가고 싶다면 길을 물어보세요.",
    exampleEn: "Excuse me, how do I get to Central Park?",
    look: { skin: SKIN[4], hair: "#111", shirt: "#23395d", pants: "#1b2a44", hat: "#1b2a44", height: 1.08 },
    spot: { x: -35, z: 22, facing: Math.PI },
  },
  {
    id: "receptionist",
    sceneId: "hotel-check-in",
    kind: "mission",
    name: "Grace",
    roleKo: "호텔 리셉션",
    teaserKo: "오늘 묵을 호텔이에요. 체크인해 볼까요?",
    exampleEn: "Hi, I have a reservation.",
    look: { skin: SKIN[0], hair: "#8a5a2b", shirt: "#f4f4f4", pants: "#2b2f3a", vest: "#7a1f2e", longHair: true, height: 0.97 },
    spot: { x: HOTEL.x1 + 1.6, z: 30, facing: Math.PI / 2 },
  },
  {
    id: "agent",
    sceneId: "subway-station",
    kind: "mission",
    name: "Marcus",
    roleKo: "지하철 역무원",
    teaserKo: "브루클린 브리지에 가려면 지하철을 타야 해요.",
    exampleEn: "Which train goes to Brooklyn?",
    look: { skin: SKIN[3], hair: "#111", shirt: "#3c4a5c", pants: "#2b2f3a", vest: "#f08a24", hat: "#2b3a4c" },
    spot: { x: -16.5, z: B[1][1].z1 + 2, facing: 0 },
  },

  // Passers-by: free chat (D-032)
  {
    id: "lily",
    sceneId: "lily",
    kind: "chat",
    name: "Lily",
    roleKo: "조깅하는 간호사",
    teaserKo: "공원에서 달리기를 하고 있어요.",
    exampleEn: "Hi! Nice day for a run, isn't it?",
    look: { skin: SKIN[1], hair: "#d8b25a", shirt: "#e84a8a", pants: "#222", longHair: true, height: 0.98 },
    route: PARK_LOOP,
    speed: 3.2,
    offset: 0,
  },
  {
    id: "sam",
    sceneId: "sam",
    kind: "chat",
    name: "Sam",
    roleKo: "개 산책 아르바이트생",
    teaserKo: "골든 리트리버 Biscuit과 산책 중이에요.",
    exampleEn: "Hi! What's your dog's name?",
    look: { skin: SKIN[0], hair: "#a0522d", shirt: "#3aa76d", pants: "#3d4f7a" },
    route: [...PARK_LOOP].reverse(),
    speed: 1.2,
    offset: 0.4,
  },
  {
    id: "rosa",
    sceneId: "rosa",
    kind: "chat",
    name: "Rosa",
    roleKo: "거리 화가",
    teaserKo: "공원 앞에서 그림을 그리고 있어요.",
    exampleEn: "Hi! Your painting is beautiful.",
    look: { skin: SKIN[2], hair: "#1d1a1f", shirt: "#f2c230", pants: "#5b4a7a", longHair: true, height: 0.96 },
    spot: { x: -10, z: PARK_EDGE - 1.6, facing: Math.PI },
  },
  {
    id: "dave",
    sceneId: "dave",
    kind: "chat",
    name: "Dave",
    roleKo: "시카고에서 온 관광객",
    teaserKo: "전광판 사진을 찍고 있어요.",
    exampleEn: "Hi! Are you a tourist too?",
    look: { skin: SKIN[0], hair: "#6b4a2b", shirt: "#ff8c42", pants: "#4a5a7a", hat: "#2a6fd6", height: 1.04 },
    spot: { x: -42, z: 30, facing: -0.6 },
  },
  {
    id: "jasmine",
    sceneId: "jasmine",
    kind: "chat",
    name: "Jasmine",
    roleKo: "브로드웨이 댄서",
    teaserKo: "리허설에 가는 길이에요.",
    exampleEn: "Hi! Where are you going?",
    look: { skin: SKIN[3], hair: "#1a1110", shirt: "#c13cff", pants: "#1f1f2e", longHair: true },
    route: aroundBlock(TIMES_SQUARE, 2, false),
    speed: 1.5,
    offset: 0.2,
  },
  {
    id: "frank",
    sceneId: "frank",
    kind: "chat",
    name: "Frank",
    roleKo: "은퇴한 택시 기사",
    teaserKo: "벤치에 앉아 쉬고 있어요.",
    exampleEn: "Hi! How's it going?",
    look: { skin: SKIN[1], hair: "#d9d9d9", shirt: "#7a8b99", pants: "#3d3a35", hat: "#4a4036", height: 0.97 },
    spot: { x: -62.45, z: 30, facing: Math.PI / 2, sit: true },
  },
  {
    id: "priya",
    sceneId: "priya",
    kind: "chat",
    name: "Priya",
    roleKo: "점심시간의 개발자",
    teaserKo: "커피를 들고 걷고 있어요.",
    exampleEn: "Hi! Is this coffee from the café?",
    look: { skin: SKIN[2], hair: "#120c0a", shirt: "#2e6f9e", pants: "#2b2f3a", longHair: true, height: 0.95 },
    route: aroundBlock(B[1][2], 2),
    speed: 1.3,
    offset: 0.55,
  },
  {
    id: "mike",
    sceneId: "mike",
    kind: "chat",
    name: "Mike",
    roleKo: "공사장 인부",
    teaserKo: "잠깐 쉬는 중이에요.",
    exampleEn: "Hi! What are you building?",
    look: { skin: SKIN[0], hair: "#3b2a1a", shirt: "#f5d742", pants: "#3a4a6a", hat: "#ffb000", vest: "#ff7a1a", height: 1.1 },
    spot: { x: 30, z: B[2][2].z0 - 1.5, facing: Math.PI },
  },
  {
    id: "emma",
    sceneId: "emma",
    kind: "chat",
    name: "Emma",
    roleKo: "영화과 대학생",
    teaserKo: "촬영 장소를 찾고 있어요.",
    exampleEn: "Hi! What are you filming?",
    look: { skin: SKIN[0], hair: "#c0392b", shirt: "#34495e", pants: "#6b5b4a", longHair: true, height: 0.95 },
    route: aroundBlock(B[2][1], 2, false),
    speed: 1.2,
    offset: 0.1,
  },
  {
    id: "carlos",
    sceneId: "carlos",
    kind: "chat",
    name: "Carlos",
    roleKo: "자전거 배달원",
    teaserKo: "다음 배달을 기다리고 있어요.",
    exampleEn: "Hi! Are you busy today?",
    look: { skin: SKIN[2], hair: "#1a1a1a", shirt: "#e63946", pants: "#222831", hat: "#e63946" },
    route: aroundBlock(B[0][2], 2),
    speed: 1.8,
    offset: 0.7,
  },
  {
    id: "helen",
    sceneId: "helen",
    kind: "chat",
    name: "Helen",
    roleKo: "산책하는 할머니",
    teaserKo: "카페 근처 벤치에 앉아 있어요.",
    exampleEn: "Hello! It's a lovely day, isn't it?",
    look: { skin: SKIN[0], hair: "#eeeeee", shirt: "#b07aa1", pants: "#4a4a5a", height: 0.92 },
    spot: { x: 48, z: B[1][2].z1 + 1.05, facing: 0, sit: true },
  },
  {
    id: "leo",
    sceneId: "leo",
    kind: "chat",
    name: "Leo",
    roleKo: "거리 음악가",
    teaserKo: "지하철 입구 옆에서 색소폰을 불어요.",
    exampleEn: "Hi! I like your music.",
    look: { skin: SKIN[4], hair: "#111", shirt: "#2d2d2d", pants: "#4b3b2b", hat: "#8b5a2b", height: 1.02 },
    spot: { x: -28, z: B[1][1].z1 + 2.2, facing: 0 },
  },
];

function PEOPLE_SPOTS(): Point[] {
  return PEOPLE.flatMap((p) => (p.spot ? [p.spot] : []));
}

/** Background walkers you cannot talk to, to make the streets busy. */
export interface Walker {
  id: string;
  look: Look;
  route: Point[];
  speed: number;
  offset: number;
}

export function buildWalkers(count = 18): Walker[] {
  const r = rand(7);
  const shirts = ["#4b5563", "#9b2226", "#264653", "#e9c46a", "#6d597a", "#2a9d8f", "#f4a261", "#3d405b", "#81b29a"];
  const hairs = ["#111", "#3b2416", "#6b4a2b", "#d8b25a", "#888", "#2a1a10"];
  const blocks = BLOCKS.flat().filter((b) => b !== TIMES_SQUARE);
  return Array.from({ length: count }, (_, i) => {
    const plaza = i % 4 === 3;
    const block = blocks[Math.floor(r() * blocks.length)];
    const d = 1.2 + r() * 1.4;
    return {
      id: `walker-${i}`,
      look: {
        skin: SKIN[Math.floor(r() * SKIN.length)],
        hair: hairs[Math.floor(r() * hairs.length)],
        shirt: shirts[Math.floor(r() * shirts.length)],
        pants: r() < 0.5 ? "#2b2f3a" : "#4a5a7a",
        longHair: r() < 0.4,
        height: 0.92 + r() * 0.16,
      },
      route: plaza ? PLAZA_LOOP : aroundBlock(block, d, r() < 0.5),
      speed: 1.1 + r() * 0.6,
      offset: r(),
    };
  });
}

// ----- traffic ----------------------------------------------------------------------------

export interface Lane {
  axis: "x" | "z";
  /** Fixed coordinate of the lane (x for avenues, z for streets). */
  at: number;
  /** +1 or -1 along the axis. */
  dir: 1 | -1;
  from: number;
  to: number;
}

// One-way avenues and two-way streets, like Manhattan.
export const LANES: Lane[] = [
  { axis: "z", at: AVENUES[0].x - 2.5, dir: -1, from: STREETS[0].z, to: WORLD.z1 },
  { axis: "z", at: AVENUES[0].x + 2.5, dir: -1, from: STREETS[0].z, to: WORLD.z1 },
  { axis: "z", at: AVENUES[1].x - 2.5, dir: 1, from: STREETS[0].z, to: WORLD.z1 },
  { axis: "z", at: AVENUES[2].x + 2.5, dir: 1, from: STREETS[0].z, to: WORLD.z1 },
  ...STREETS.flatMap((s) => [
    { axis: "x" as const, at: s.z - 2.5, dir: -1 as const, from: WORLD.x0, to: WORLD.x1 },
    { axis: "x" as const, at: s.z + 2.5, dir: 1 as const, from: WORLD.x0, to: WORLD.x1 },
  ]),
];

// ----- geometry helpers -------------------------------------------------------------------

export function inRect(p: Point, r: Rect): boolean {
  return p.x >= r.x0 && p.x <= r.x1 && p.z >= r.z0 && p.z <= r.z1;
}

export function grow(r: Rect, d: number): Rect {
  return { x0: r.x0 - d, z0: r.z0 - d, x1: r.x1 + d, z1: r.z1 + d };
}

export function propRect(p: Prop): Rect {
  const [w, d] = PROP_SIZE[p.kind];
  const turned = Math.abs(Math.sin(p.rot)) > 0.5;
  const hw = (turned ? d : w) / 2;
  const hd = (turned ? w : d) / 2;
  return { x0: p.x - hw, x1: p.x + hw, z0: p.z - hd, z1: p.z + hd };
}

/** Everything solid on the ground, as rectangles. */
export function buildColliders(buildings = buildBuildings(), trees = buildTrees()): Rect[] {
  return [
    ...buildings,
    POND,
    ...PROPS.map(propRect),
    ...trees.map((t) => ({ x0: t.x - 0.5, x1: t.x + 0.5, z0: t.z - 0.5, z1: t.z + 0.5 })),
  ];
}

/** Position and heading at `distance` meters along a closed route. */
export function routePoint(route: Point[], distance: number): Point & { heading: number } {
  const segs = route.map((a, i) => {
    const b = route[(i + 1) % route.length];
    return { a, b, len: Math.hypot(b.x - a.x, b.z - a.z) };
  });
  const total = segs.reduce((s, g) => s + g.len, 0);
  let d = ((distance % total) + total) % total;
  for (const g of segs) {
    if (d <= g.len) {
      const t = g.len === 0 ? 0 : d / g.len;
      return {
        x: g.a.x + (g.b.x - g.a.x) * t,
        z: g.a.z + (g.b.z - g.a.z) * t,
        heading: Math.atan2(g.b.x - g.a.x, g.b.z - g.a.z),
      };
    }
    d -= g.len;
  }
  const last = segs[segs.length - 1];
  return { ...last.b, heading: Math.atan2(last.b.x - last.a.x, last.b.z - last.a.z) };
}

export function routeLength(route: Point[]): number {
  return route.reduce((s, a, i) => {
    const b = route[(i + 1) % route.length];
    return s + Math.hypot(b.x - a.x, b.z - a.z);
  }, 0);
}

/** Move a circle by (dx, dz), sliding along rectangles instead of passing through. */
export function moveCircle(p: Point, dx: number, dz: number, radius: number, solids: Rect[]): Point {
  const hits = (q: Point) =>
    q.x - radius < WORLD.x0 ||
    q.x + radius > WORLD.x1 ||
    q.z - radius < WORLD.z0 ||
    q.z + radius > WORLD.z1 ||
    solids.some((r) => q.x + radius > r.x0 && q.x - radius < r.x1 && q.z + radius > r.z0 && q.z - radius < r.z1);
  let next = { x: p.x + dx, z: p.z };
  if (hits(next)) next = { x: p.x, z: p.z };
  const moved = { x: next.x, z: next.z + dz };
  return hits(moved) ? next : moved;
}

export const TALK_DISTANCE = 2.6;
