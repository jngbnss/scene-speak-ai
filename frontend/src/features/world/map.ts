/**
 * The New York map: a grid of tiles built from rectangles, plus the NPCs standing on it.
 * North is up: Central Park on top, then 59th Street, Midtown blocks below.
 * Everything is drawn in code (draw.ts), so there are no third-party image assets.
 */

export type Tile =
  | "grass"
  | "tree"
  | "path"
  | "pond"
  | "road"
  | "laneH"
  | "laneV"
  | "cross"
  | "walk"
  | "plaza"
  | "brick"
  | "office"
  | "hotel"
  | "cafe"
  | "station"
  | "billboard"
  | "subway"
  | "cart"
  | "lamp"
  | "bench"
  | "taxi";

export const TILE = 16;
export const COLS = 44;
export const ROWS = 32;

const SOLID: ReadonlySet<Tile> = new Set<Tile>([
  "tree",
  "pond",
  "brick",
  "office",
  "hotel",
  "cafe",
  "station",
  "billboard",
  "subway",
  "cart",
  "lamp",
  "bench",
  "taxi",
]);

export type Look = {
  skin: string;
  hair: string;
  shirt: string;
  pants: string;
  hat?: string;
  apron?: string;
  vest?: string;
};

export interface NpcDef {
  id: string;
  /** Backend scene id (scenes/*.yaml or scenes/talks/*.yaml). */
  sceneId: string;
  name: string;
  roleKo: string;
  /** One line shown when the player walks up, before talking. */
  teaserKo: string;
  /** Example line shown in the empty input box. */
  exampleEn: string;
  x: number; // tile coordinates of the NPC's feet
  y: number;
  facing: Dir;
  look: Look;
}

export interface Ambient {
  id: string;
  x: number;
  y: number;
  facing: Dir;
  look: Look;
  /** What they say if you walk up (no conversation, just atmosphere). */
  lineKo: string;
}

export type Dir = "down" | "up" | "left" | "right";

export type TileMap = Tile[][];

function fill(map: TileMap, tile: Tile, x0: number, y0: number, x1: number, y1: number): void {
  for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) if (map[y]?.[x] !== undefined) map[y][x] = tile;
}

// Avenues run north-south, streets east-west. Each road is 2 tiles with sidewalks beside it.
export const AVENUES = [13, 29]; // left column of each avenue
export const STREETS = [10, 21]; // top row of each street

export function buildMap(): TileMap {
  const map: TileMap = Array.from({ length: ROWS }, () => Array<Tile>(COLS).fill("walk"));

  // Central Park (rows 0-8)
  fill(map, "grass", 0, 0, COLS - 1, 8);
  fill(map, "path", 0, 5, COLS - 1, 5);
  fill(map, "path", 21, 0, 22, 8);
  fill(map, "pond", 30, 1, 37, 3);
  const trees = [
    [1, 1], [4, 2], [7, 1], [10, 3], [13, 1], [16, 2], [18, 7], [25, 1], [27, 3], [39, 2],
    [41, 1], [2, 7], [6, 7], [9, 6], [14, 7], [25, 7], [28, 6], [33, 7], [37, 6], [42, 7],
    [40, 4], [12, 2], [17, 4], [3, 4],
  ];
  for (const [x, y] of trees) map[y][x] = "tree";
  for (const x of [8, 18, 26, 34]) map[4][x] = "bench";

  // Roads
  for (const y of STREETS) {
    fill(map, "road", 0, y, COLS - 1, y + 1);
    fill(map, "laneH", 0, y, COLS - 1, y);
  }
  for (const x of AVENUES) {
    fill(map, "road", x, STREETS[0], x + 1, ROWS - 1);
    fill(map, "laneV", x, STREETS[0] + 2, x, ROWS - 1);
  }
  // Crosswalks where avenues meet streets
  for (const ax of AVENUES) {
    for (const sy of STREETS) {
      fill(map, "road", ax, sy, ax + 1, sy + 1);
      // across the street, on both sides of the avenue
      fill(map, "cross", ax - 1, sy, ax - 1, sy + 1);
      fill(map, "cross", ax + 2, sy, ax + 2, sy + 1);
      // across the avenue, above and below the street (the avenue starts at 59th St)
      for (const row of [sy - 1, sy + 2]) {
        if (row > STREETS[0] + 1) fill(map, "cross", ax, row, ax + 1, row);
      }
    }
  }

  // Blocks between 59th St (rows 10-11) and 45th St (rows 21-22)
  // West block: the hotel
  fill(map, "hotel", 0, 13, 11, 18);
  // Middle block: Times Square plaza with billboards
  fill(map, "plaza", 16, 13, 27, 19);
  fill(map, "billboard", 16, 13, 19, 14);
  fill(map, "billboard", 24, 13, 27, 14);
  fill(map, "billboard", 16, 17, 16, 19);
  fill(map, "billboard", 27, 17, 27, 19);
  // East block: the café between brick buildings
  fill(map, "brick", 32, 13, 35, 18);
  fill(map, "cafe", 36, 13, 41, 18);
  fill(map, "brick", 42, 13, 43, 18);

  // South blocks (rows 24-31)
  fill(map, "office", 0, 24, 11, 31);
  fill(map, "station", 16, 24, 27, 31);
  fill(map, "brick", 32, 24, 43, 31);

  // Street furniture
  map[23][20] = "subway";
  map[23][21] = "subway";
  map[23][38] = "cart";
  for (const [x, y] of [[12, 12], [12, 23], [31, 12], [31, 23], [15, 23], [28, 12]]) map[y][x] = "lamp";
  map[STREETS[1]][4] = "taxi";
  map[STREETS[1] + 1][36] = "taxi";
  map[16][AVENUES[0]] = "taxi";
  return map;
}

export function isSolid(map: TileMap, x: number, y: number): boolean {
  const tx = Math.floor(x);
  const ty = Math.floor(y);
  if (tx < 0 || ty < 0 || tx >= COLS || ty >= ROWS) return true;
  return SOLID.has(map[ty][tx]);
}

const SKIN = ["#f1c7a5", "#d9a37c", "#a8714a", "#7a4a2b"];

export const PLAYER_LOOK: Look = {
  skin: SKIN[0],
  hair: "#1d1a1f",
  shirt: "#2f6fd6",
  pants: "#2b2f3a",
};

export const PLAYER_START = { x: 22, y: 12.5 };

export const NPCS: NpcDef[] = [
  {
    id: "barista",
    exampleEn: "Can I get a large hot latte?",
    sceneId: "new-york-cafe",
    name: "Maya",
    roleKo: "카페 바리스타",
    teaserKo: "카페 앞에서 주문을 받고 있어요.",
    x: 38.5,
    y: 19.6,
    facing: "down",
    look: { skin: SKIN[1], hair: "#3b2416", shirt: "#ffffff", pants: "#30343c", apron: "#1f7a4d" },
  },
  {
    id: "vendor",
    exampleEn: "Can I get a hot dog, please?",
    sceneId: "hot-dog-stand",
    name: "Tony",
    roleKo: "핫도그 노점상",
    teaserKo: "고소한 냄새가 나요. 점심으로 어때요?",
    x: 39.5,
    y: 23.6,
    facing: "left",
    look: { skin: SKIN[0], hair: "#5a3a22", shirt: "#d23a2e", pants: "#30343c", hat: "#d23a2e", apron: "#f4f4f4" },
  },
  {
    id: "officer",
    exampleEn: "Excuse me, can you help me?",
    sceneId: "times-square-directions",
    name: "Officer Davis",
    roleKo: "경찰관",
    teaserKo: "센트럴 파크에 가고 싶다면 길을 물어보세요.",
    x: 22,
    y: 16.6,
    facing: "down",
    look: { skin: SKIN[3], hair: "#111", shirt: "#23395d", pants: "#1b2a44", hat: "#1b2a44" },
  },
  {
    id: "receptionist",
    exampleEn: "Hi, I have a reservation.",
    sceneId: "hotel-check-in",
    name: "Grace",
    roleKo: "호텔 리셉션",
    teaserKo: "오늘 묵을 호텔이에요. 체크인해 볼까요?",
    x: 6.5,
    y: 19.6,
    facing: "down",
    look: { skin: SKIN[0], hair: "#8a5a2b", shirt: "#f4f4f4", pants: "#2b2f3a", vest: "#7a1f2e" },
  },
  {
    id: "agent",
    exampleEn: "Which train goes to Brooklyn?",
    sceneId: "subway-station",
    name: "Marcus",
    roleKo: "지하철 역무원",
    teaserKo: "브루클린 브리지에 가려면 지하철을 타야 해요.",
    x: 23,
    y: 23.6,
    facing: "down",
    look: { skin: SKIN[2], hair: "#111", shirt: "#3c4a5c", pants: "#2b2f3a", vest: "#f08a24", hat: "#2b3a4c" },
  },
];

export const AMBIENT: Ambient[] = [
  {
    id: "jogger",
    x: 10,
    y: 5.6,
    facing: "right",
    look: { skin: SKIN[1], hair: "#d8b25a", shirt: "#e84a8a", pants: "#222" },
    lineKo: "\"Beautiful day for a run!\" — 조깅하는 사람이 지나가요.",
  },
  {
    id: "tourist",
    x: 19,
    y: 18.6,
    facing: "up",
    look: { skin: SKIN[0], hair: "#2a2a2a", shirt: "#f2c230", pants: "#4a5a7a" },
    lineKo: "\"Wow, look at those lights!\" — 관광객이 전광판을 보고 있어요.",
  },
  {
    id: "businessman",
    x: 8,
    y: 23.6,
    facing: "right",
    look: { skin: SKIN[2], hair: "#111", shirt: "#4b5563", pants: "#1f2937" },
    lineKo: "\"Sorry, I'm late for a meeting!\" — 바쁘게 지나가네요.",
  },
];

export const TALK_DISTANCE = 1.7;
