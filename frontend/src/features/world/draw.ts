/** Pixel-art drawing in code: map tiles (pre-rendered once) and characters (every frame). */
import { COLS, ROWS, TILE, type Dir, type Look, type Tile, type TileMap } from "./map";

type Ctx = CanvasRenderingContext2D;

/** Small deterministic noise so repeated tiles don't look identical. */
function hash(x: number, y: number): number {
  let h = (x * 374761393 + y * 668265263) | 0;
  h = (h ^ (h >>> 13)) * 1274126177;
  return ((h ^ (h >>> 16)) >>> 0) / 4294967295;
}

function px(ctx: Ctx, color: string, x: number, y: number, w = 1, h = 1): void {
  ctx.fillStyle = color;
  ctx.fillRect(x, y, w, h);
}

const C = {
  asphalt: "#3b3e45",
  asphalt2: "#363940",
  lane: "#e6c34a",
  zebra: "#e9e9e4",
  walk: "#bdb8ad",
  walkLine: "#a8a397",
  grass: "#5d9b48",
  grass2: "#69a953",
  leaf: "#2f6e34",
  leafDark: "#24562a",
  leafLight: "#4b8f45",
  trunk: "#6b4a2b",
  path: "#d8c79c",
  water: "#3d78b8",
  waterLight: "#6aa3dc",
  brick: "#9a4a35",
  brickDark: "#7f3a2a",
  mortar: "#b8735d",
  office: "#7c8693",
  officeDark: "#5f6874",
  glass: "#a9cbe6",
  glassDark: "#6f9cc2",
  hotel: "#cdb898",
  hotelDark: "#a8936f",
  cafe: "#2d5a4b",
  station: "#d9c9a5",
  stationDark: "#b9a682",
  plaza: "#c9a9a6",
  plaza2: "#bf9d9a",
  ink: "#1d1f24",
};

const NEON = ["#ff3d7f", "#36d6ff", "#ffd23d", "#7cff6b", "#b36bff", "#ff8a3d"];

function window(ctx: Ctx, x: number, y: number, lit: boolean): void {
  px(ctx, C.ink, x, y, 5, 6);
  px(ctx, lit ? "#ffe9a3" : C.glass, x + 1, y + 1, 3, 4);
  if (!lit) px(ctx, C.glassDark, x + 1, y + 3, 3, 2);
}

function drawTile(ctx: Ctx, map: TileMap, tx: number, ty: number): void {
  const t = map[ty][tx];
  const x = tx * TILE;
  const y = ty * TILE;
  const r = hash(tx, ty);
  const below = map[ty + 1]?.[tx];
  const isBottom = below !== t;
  const base: Partial<Record<Tile, string>> = {
    road: C.asphalt,
    laneH: C.asphalt,
    laneV: C.asphalt,
    cross: C.asphalt,
    taxi: C.asphalt,
    walk: C.walk,
    lamp: C.walk,
    subway: C.walk,
    cart: C.walk,
    grass: C.grass,
    tree: C.grass,
    bench: C.grass,
    path: C.path,
    pond: C.water,
    plaza: C.plaza,
    billboard: C.ink,
  };
  // Furniture standing on a sidewalk vs. on a park path
  const ground = t === "bench" && map[ty][tx - 1] === "path" ? C.path : base[t];
  if (ground) px(ctx, ground, x, y, TILE, TILE);

  switch (t) {
    case "road":
    case "laneH":
    case "laneV":
    case "taxi":
      for (let i = 0; i < 3; i++) px(ctx, C.asphalt2, x + Math.floor(hash(tx + i, ty) * 15), y + Math.floor(hash(tx, ty + i) * 15));
      if (t === "laneH") for (let i = 0; i < TILE; i += 8) px(ctx, C.lane, x + i, y + TILE - 1, 5, 2);
      if (t === "laneV") for (let i = 0; i < TILE; i += 8) px(ctx, C.lane, x + TILE - 1, y + i, 2, 5);
      if (t === "taxi") drawTaxi(ctx, x, y);
      break;
    case "cross": {
      const vertical = map[ty][tx - 1] !== "road" && map[ty][tx + 1] !== "road";
      for (let i = 1; i < TILE; i += 4) {
        if (vertical) px(ctx, C.zebra, x + 2, y + i, TILE - 4, 2);
        else px(ctx, C.zebra, x + i, y + 2, 2, TILE - 4);
      }
      break;
    }
    case "walk":
    case "lamp":
    case "subway":
    case "cart":
      px(ctx, C.walkLine, x, y, TILE, 1);
      px(ctx, C.walkLine, x, y, 1, TILE);
      if (r > 0.85) px(ctx, C.walkLine, x + 6, y + 9, 2, 1);
      if (t === "lamp") {
        px(ctx, C.ink, x + 7, y + 2, 2, 13);
        px(ctx, "#ffe08a", x + 5, y, 6, 3);
        px(ctx, C.ink, x + 5, y + 14, 6, 2);
      }
      if (t === "subway") drawSubway(ctx, x, y, map[ty][tx - 1] === "subway");
      if (t === "cart") drawCart(ctx, x, y);
      break;
    case "grass":
    case "tree":
    case "bench":
      if (r > 0.5) px(ctx, C.grass2, x + Math.floor(r * 12), y + Math.floor(hash(ty, tx) * 12), 2, 1);
      if (r > 0.8) px(ctx, "#f2e36b", x + 3 + Math.floor(r * 8), y + 4, 1, 1);
      if (t === "tree") {
        px(ctx, "rgba(0,0,0,0.18)", x + 2, y + 12, 12, 3);
        px(ctx, C.trunk, x + 7, y + 9, 2, 6);
        px(ctx, C.leafDark, x + 1, y + 1, 14, 10);
        px(ctx, C.leaf, x + 2, y, 12, 9);
        px(ctx, C.leafLight, x + 4, y + 2, 4, 3);
      }
      if (t === "bench") {
        px(ctx, "#7a5230", x + 1, y + 6, 14, 3);
        px(ctx, "#7a5230", x + 1, y + 10, 14, 2);
        px(ctx, C.ink, x + 2, y + 12, 1, 3);
        px(ctx, C.ink, x + 13, y + 12, 1, 3);
      }
      break;
    case "path":
      if (r > 0.6) px(ctx, "#c9b88b", x + Math.floor(r * 13), y + Math.floor(hash(ty, tx) * 13), 2, 2);
      break;
    case "pond":
      if (r > 0.55) px(ctx, C.waterLight, x + Math.floor(r * 10), y + 5 + Math.floor(hash(ty, tx) * 6), 4, 1);
      break;
    case "plaza":
      if ((tx + ty) % 2 === 0) px(ctx, C.plaza2, x, y, TILE, TILE);
      break;
    case "billboard":
      drawBillboard(ctx, x, y, NEON[Math.floor(r * NEON.length)], r);
      break;
    case "brick":
      px(ctx, C.brick, x, y, TILE, TILE);
      for (let row = 0; row < TILE; row += 4) {
        px(ctx, C.mortar, x, y + row, TILE, 1);
        const off = (row / 4 + ty) % 2 === 0 ? 0 : 4;
        for (let col = off; col < TILE; col += 8) px(ctx, C.mortar, x + col, y + row, 1, 4);
      }
      if (ty % 2 === 0) window(ctx, x + 5, y + 5, r > 0.75);
      if (isBottom) px(ctx, C.brickDark, x, y + 12, TILE, 4);
      break;
    case "office":
      px(ctx, C.office, x, y, TILE, TILE);
      px(ctx, C.officeDark, x, y, 1, TILE);
      px(ctx, C.glassDark, x + 3, y + 2, 4, 12);
      px(ctx, C.glass, x + 9, y + 2, 4, 12);
      if (r > 0.8) px(ctx, "#ffe9a3", x + 9, y + 2, 4, 5);
      break;
    case "hotel":
      px(ctx, C.hotel, x, y, TILE, TILE);
      px(ctx, C.hotelDark, x, y + TILE - 1, TILE, 1);
      if (!isBottom) window(ctx, x + 5, y + 4, r > 0.7);
      else {
        px(ctx, "#7a1f2e", x, y, TILE, 5);
        for (let i = 0; i < TILE; i += 4) px(ctx, "#9b2c3e", x + i, y + 4, 2, 2);
        if (tx === 5 || tx === 6) px(ctx, "#3a2a1a", x + 2, y + 6, 12, 10);
        if (tx === 5 || tx === 6) px(ctx, "#e7c26a", x + (tx === 5 ? 13 : 2), y + 10, 1, 2);
      }
      break;
    case "cafe":
      px(ctx, C.cafe, x, y, TILE, TILE);
      if (!isBottom) window(ctx, x + 5, y + 4, r > 0.5);
      else {
        for (let i = 0; i < TILE; i += 4) px(ctx, i % 8 === 0 ? "#1f7a4d" : "#f2f2ec", x + i, y, 4, 5);
        px(ctx, C.glass, x + 1, y + 6, 14, 9);
        px(ctx, "#ffe2a8", x + 2, y + 8, 5, 4);
        if (tx === 38) px(ctx, "#4a2f1d", x + 4, y + 6, 8, 10);
      }
      break;
    case "station":
      px(ctx, C.station, x, y, TILE, TILE);
      px(ctx, C.stationDark, x, y, TILE, 1);
      if (isBottom || ty % 3 === 1) {
        px(ctx, C.stationDark, x + 3, y + 3, 10, 13);
        px(ctx, "#5e6f86", x + 4, y + 4, 8, 12);
        px(ctx, C.station, x + 4, y + 3, 8, 2);
      }
      break;
  }
}

function drawTaxi(ctx: Ctx, x: number, y: number): void {
  px(ctx, "rgba(0,0,0,0.25)", x + 1, y + 12, 15, 3);
  px(ctx, "#f2c230", x + 1, y + 4, 14, 8);
  px(ctx, "#d9a91e", x + 1, y + 10, 14, 2);
  px(ctx, C.glass, x + 4, y + 5, 8, 3);
  px(ctx, C.ink, x + 3, y + 11, 3, 3);
  px(ctx, C.ink, x + 10, y + 11, 3, 3);
  px(ctx, C.ink, x + 6, y + 2, 4, 2);
  for (let i = 2; i < 14; i += 2) px(ctx, C.ink, x + i, y + 9, 1, 1);
}

function drawSubway(ctx: Ctx, x: number, y: number, right: boolean): void {
  px(ctx, "#2f3a33", x + 1, y + 3, 14, 12);
  for (let i = 4; i < 14; i += 3) px(ctx, "#5a655c", x + 2, y + i, 12, 1);
  px(ctx, "#1f7a4d", x, y + 2, TILE, 2);
  if (!right) {
    px(ctx, C.ink, x + 1, y - 6, 1, 8);
    px(ctx, "#2fbf6a", x - 1, y - 9, 5, 4);
  }
}

function drawCart(ctx: Ctx, x: number, y: number): void {
  px(ctx, "rgba(0,0,0,0.2)", x + 1, y + 13, 14, 3);
  px(ctx, "#c9ced6", x + 1, y + 7, 14, 6);
  px(ctx, "#8f96a1", x + 1, y + 12, 14, 1);
  px(ctx, C.ink, x + 3, y + 13, 3, 3);
  px(ctx, C.ink, x + 10, y + 13, 3, 3);
  px(ctx, C.ink, x + 7, y - 4, 1, 11);
  for (let i = 0; i < 16; i += 4) px(ctx, i % 8 === 0 ? "#d23a2e" : "#f2c230", x + i, y - 6, 4, 3);
  px(ctx, "#d23a2e", x + 3, y + 8, 10, 2);
}

function drawBillboard(ctx: Ctx, x: number, y: number, color: string, r: number): void {
  px(ctx, "#111318", x, y, TILE, TILE);
  px(ctx, color, x + 1, y + 1, 14, 14);
  px(ctx, "#ffffff", x + 3, y + 4 + Math.floor(r * 4), 8 + Math.floor(r * 4), 2);
  px(ctx, "rgba(0,0,0,0.25)", x + 3, y + 9, 10, 2);
}

function label(ctx: Ctx, text: string, cx: number, cy: number, bg: string, fg = "#fff"): void {
  ctx.font = "bold 7px monospace";
  const w = Math.ceil(ctx.measureText(text).width) + 6;
  px(ctx, bg, Math.round(cx - w / 2), cy - 6, w, 9);
  ctx.fillStyle = fg;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, Math.round(cx), cy - 1);
}

/** Renders the whole static map once (1 px = 1 map pixel). */
export function renderMap(map: TileMap): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = COLS * TILE;
  canvas.height = ROWS * TILE;
  const ctx = canvas.getContext("2d");
  if (!ctx) return canvas;
  for (let ty = 0; ty < ROWS; ty++) for (let tx = 0; tx < COLS; tx++) drawTile(ctx, map, tx, ty);
  // Furniture that pokes above its tile (lamps, cart umbrella) is drawn again on top.
  for (let ty = 0; ty < ROWS; ty++)
    for (let tx = 0; tx < COLS; tx++) if (["subway", "cart"].includes(map[ty][tx])) drawTile(ctx, map, tx, ty);

  label(ctx, "CENTRAL PARK", 22 * TILE, 2 * TILE + 4, "#2f6e34");
  label(ctx, "W 59 ST", 6 * TILE, 11 * TILE + 2, "#1f7a4d");
  label(ctx, "W 45 ST", 6 * TILE, 22 * TILE + 2, "#1f7a4d");
  label(ctx, "7 AV", 14 * TILE, 27 * TILE, "#1f7a4d");
  label(ctx, "5 AV", 30 * TILE, 27 * TILE, "#1f7a4d");
  label(ctx, "HOTEL", 6 * TILE, 14 * TILE + 8, "#7a1f2e");
  label(ctx, "CAFÉ", 39 * TILE, 14 * TILE + 8, "#1f7a4d");
  label(ctx, "TIMES SQ", 22 * TILE, 13 * TILE + 8, "#c2185b");
  label(ctx, "GRAND CENTRAL", 22 * TILE, 26 * TILE, "#6b5a3a");
  label(ctx, "SUBWAY", 21 * TILE, 22 * TILE + 12, "#1f7a4d");
  label(ctx, "HOT DOGS", 38.5 * TILE, 22 * TILE + 12, "#d23a2e");
  return canvas;
}

/**
 * A person, 10x15 map pixels, feet at (x, y). `step` alternates legs while walking.
 * `p` is the screen size of one map pixel.
 */
export function drawPerson(
  ctx: Ctx,
  x: number,
  y: number,
  p: number,
  look: Look,
  dir: Dir,
  step: number,
): void {
  const ox = Math.round(x - 5 * p);
  const oy = Math.round(y - 15 * p);
  const r = (c: string, ux: number, uy: number, w = 1, h = 1) => {
    ctx.fillStyle = c;
    ctx.fillRect(ox + ux * p, oy + uy * p, w * p, h * p);
  };
  const side = dir === "left" || dir === "right";
  // shadow
  ctx.fillStyle = "rgba(0,0,0,0.22)";
  ctx.fillRect(ox + 1 * p, oy + 14 * p, 8 * p, 2 * p);
  // legs
  const lift = step % 2 === 1 ? 1 : 0;
  if (side) {
    r(look.pants, 3, 10, 2, 4 - lift);
    r(look.pants, 5, 10, 2, 4 - (1 - lift) * (step ? 1 : 0));
    r(C.ink, 3, 14 - lift, 2, 1);
    r(C.ink, 5, 14, 2, 1);
  } else {
    r(look.pants, 2, 10, 2, 4 - lift);
    r(look.pants, 6, 10, 2, 4 - (step ? 1 - lift : 0));
    r(C.ink, 2, 14 - lift, 2, 1);
    r(C.ink, 6, 14 - (step ? 1 - lift : 0), 2, 1);
  }
  // body
  r(look.shirt, 1, 6, 8, 5);
  if (look.vest) {
    r(look.vest, 1, 6, 2, 5);
    r(look.vest, 7, 6, 2, 5);
  }
  if (look.apron && !side) r(look.apron, 3, 7, 4, 4);
  if (look.apron && side) r(look.apron, dir === "left" ? 1 : 6, 7, 3, 4);
  // arms
  if (side) r(look.skin, dir === "left" ? 4 : 5, 8 + (step ? lift : 0), 1, 3);
  else {
    r(look.skin, 0, 7, 1, 3);
    r(look.skin, 9, 7, 1, 3);
  }
  // head
  r(look.skin, 2, 1, 6, 5);
  r(look.hair, 2, 0, 6, 2);
  if (dir === "up") r(look.hair, 2, 1, 6, 4);
  else if (dir === "left") r(look.hair, 6, 1, 2, 3);
  else if (dir === "right") r(look.hair, 2, 1, 2, 3);
  else {
    r(look.hair, 2, 1, 1, 2);
    r(look.hair, 7, 1, 1, 2);
  }
  // eyes
  if (dir === "down") {
    r(C.ink, 3, 3);
    r(C.ink, 6, 3);
  } else if (dir === "left") r(C.ink, 3, 3);
  else if (dir === "right") r(C.ink, 6, 3);
  if (look.hat) {
    r(look.hat, 1, -1, 8, 2);
    if (dir === "down") r(look.hat, 2, 1, 6, 1);
    if (dir === "left") r(look.hat, 0, 0, 2, 1);
    if (dir === "right") r(look.hat, 8, 0, 2, 1);
  }
}

/** Floating marker above an NPC: "!" for a new mission, a check for a cleared one. */
export function drawMarker(ctx: Ctx, x: number, y: number, p: number, cleared: boolean, bob: number): void {
  const cx = Math.round(x);
  const top = Math.round(y - 22 * p + bob * p);
  ctx.fillStyle = cleared ? "#2e9d5b" : "#ffcc33";
  ctx.strokeStyle = C.ink;
  ctx.lineWidth = Math.max(1, p / 2);
  ctx.beginPath();
  ctx.arc(cx, top, 3.5 * p, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = C.ink;
  if (cleared) {
    ctx.fillRect(cx - 2 * p, top, p, p);
    ctx.fillRect(cx - p, top + p, p, p);
    ctx.fillRect(cx, top, p, p);
    ctx.fillRect(cx + p, top - p, p, p);
  } else {
    ctx.fillRect(cx - p / 2, top - 2.5 * p, p, 3 * p);
    ctx.fillRect(cx - p / 2, top + 1.5 * p, p, p);
  }
}
