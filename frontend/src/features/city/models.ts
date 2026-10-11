/**
 * Low-poly people, cars and street furniture, built from three.js primitives in code
 * (no model files, so no asset licenses to track).
 */
import * as THREE from "three";

import type { Billboard, Building, Look, Prop } from "./layout";

const materials = new Map<string, THREE.MeshStandardMaterial>();

/** Shared material per color, so hundreds of meshes reuse a handful of materials. */
export function mat(color: string, opts: { rough?: number; metal?: number; emissive?: string } = {}): THREE.MeshStandardMaterial {
  const key = `${color}|${opts.rough ?? 0.8}|${opts.metal ?? 0}|${opts.emissive ?? ""}`;
  let m = materials.get(key);
  if (!m) {
    m = new THREE.MeshStandardMaterial({
      color,
      roughness: opts.rough ?? 0.8,
      metalness: opts.metal ?? 0,
      emissive: opts.emissive ? new THREE.Color(opts.emissive) : undefined,
      emissiveIntensity: opts.emissive ? 0.6 : 0,
    });
    materials.set(key, m);
  }
  return m;
}

export function disposeShared(): void {
  materials.forEach((m) => m.dispose());
  materials.clear();
}

function mesh(geo: THREE.BufferGeometry, material: THREE.Material, shadow = true): THREE.Mesh {
  const m = new THREE.Mesh(geo, material);
  m.castShadow = shadow;
  m.receiveShadow = true;
  return m;
}

// ----- people -----------------------------------------------------------------------------

export interface PersonRig {
  root: THREE.Group;
  /** Advance the walk cycle; speed in m/s (0 = standing). */
  animate: (dt: number, speed: number) => void;
  sit: () => void;
}

interface Limb {
  hip: THREE.Group;
  knee: THREE.Group;
}

/** A person about 1.75 m tall standing at the origin, facing +z. */
export function makePerson(look: Look): PersonRig {
  const root = new THREE.Group();
  const body = new THREE.Group();
  root.add(body);
  const skin = mat(look.skin, { rough: 0.6 });
  const shirt = mat(look.shirt);
  const pants = mat(look.pants);
  const shoes = mat(look.shoes ?? "#1b1b1f", { rough: 0.5 });
  const hair = mat(look.hair, { rough: 0.9 });

  const HIP = 0.92;
  const legs: Limb[] = [-1, 1].map((side) => {
    const hip = new THREE.Group();
    hip.position.set(side * 0.1, HIP, 0);
    const thigh = mesh(new THREE.CapsuleGeometry(0.075, 0.34, 3, 8), pants);
    thigh.position.y = -0.22;
    hip.add(thigh);
    const knee = new THREE.Group();
    knee.position.y = -0.45;
    hip.add(knee);
    const shin = mesh(new THREE.CapsuleGeometry(0.065, 0.32, 3, 8), pants);
    shin.position.y = -0.21;
    knee.add(shin);
    const shoe = mesh(new THREE.BoxGeometry(0.12, 0.08, 0.24), shoes);
    shoe.position.set(0, -0.43, 0.05);
    knee.add(shoe);
    body.add(hip);
    return { hip, knee };
  });

  // Torso and hips
  const pelvis = mesh(new THREE.CylinderGeometry(0.17, 0.16, 0.16, 10), pants);
  pelvis.position.y = HIP + 0.02;
  body.add(pelvis);
  const torso = mesh(new THREE.CapsuleGeometry(0.17, 0.32, 4, 10), shirt);
  torso.scale.set(1.15, 1, 0.75);
  torso.position.y = HIP + 0.32;
  body.add(torso);
  if (look.apron) {
    const apron = mesh(new THREE.BoxGeometry(0.34, 0.62, 0.02), mat(look.apron));
    apron.position.set(0, HIP + 0.15, 0.14);
    body.add(apron);
  }
  if (look.vest) {
    const vest = mesh(new THREE.CapsuleGeometry(0.175, 0.24, 4, 10), mat(look.vest));
    vest.scale.set(1.18, 1, 0.8);
    vest.position.y = HIP + 0.36;
    body.add(vest);
  }

  // Arms
  const arms: Limb[] = [-1, 1].map((side) => {
    const shoulder = new THREE.Group();
    shoulder.position.set(side * 0.25, HIP + 0.55, 0);
    const upper = mesh(new THREE.CapsuleGeometry(0.06, 0.24, 3, 8), shirt);
    upper.position.y = -0.15;
    shoulder.add(upper);
    const elbow = new THREE.Group();
    elbow.position.y = -0.3;
    shoulder.add(elbow);
    const fore = mesh(new THREE.CapsuleGeometry(0.05, 0.22, 3, 8), skin);
    fore.position.y = -0.14;
    elbow.add(fore);
    const hand = mesh(new THREE.SphereGeometry(0.055, 8, 6), skin);
    hand.position.y = -0.3;
    elbow.add(hand);
    shoulder.rotation.z = side * 0.06;
    body.add(shoulder);
    return { hip: shoulder, knee: elbow };
  });

  // Head
  const neck = mesh(new THREE.CylinderGeometry(0.055, 0.06, 0.1, 8), skin);
  neck.position.y = HIP + 0.66;
  body.add(neck);
  const head = new THREE.Group();
  head.position.y = HIP + 0.82;
  body.add(head);
  const skull = mesh(new THREE.SphereGeometry(0.13, 14, 12), skin);
  skull.scale.set(0.95, 1.08, 1);
  head.add(skull);
  const nose = mesh(new THREE.SphereGeometry(0.022, 6, 5), skin, false);
  nose.position.set(0, -0.01, 0.13);
  head.add(nose);
  for (const side of [-1, 1]) {
    const eye = mesh(new THREE.SphereGeometry(0.017, 6, 5), mat("#1a1a1a", { rough: 0.3 }), false);
    eye.position.set(side * 0.045, 0.02, 0.118);
    head.add(eye);
    const ear = mesh(new THREE.SphereGeometry(0.03, 6, 5), skin, false);
    ear.scale.set(0.5, 1, 0.8);
    ear.position.set(side * 0.125, 0, 0);
    head.add(ear);
  }
  const cap = mesh(new THREE.SphereGeometry(0.137, 14, 10, 0, Math.PI * 2, 0, Math.PI * 0.55), hair);
  cap.scale.set(0.97, 1.1, 1.04);
  cap.rotation.x = -0.25;
  cap.position.z = -0.01;
  head.add(cap);
  if (look.longHair) {
    const back = mesh(new THREE.CapsuleGeometry(0.11, 0.2, 4, 10), hair);
    back.scale.set(1.15, 1, 0.55);
    back.position.set(0, -0.12, -0.08);
    head.add(back);
  }
  if (look.hat) {
    const hatMat = mat(look.hat);
    const crown = mesh(new THREE.CylinderGeometry(0.13, 0.14, 0.1, 12), hatMat);
    crown.position.y = 0.1;
    head.add(crown);
    const brim = mesh(new THREE.CylinderGeometry(0.11, 0.11, 0.015, 12, 1, false, -Math.PI / 2, Math.PI), hatMat);
    brim.scale.set(1, 1, 1.4);
    brim.position.set(0, 0.06, 0.08);
    head.add(brim);
  }

  const scale = look.height ?? 1;
  root.scale.setScalar(scale);

  let phase = Math.random() * Math.PI * 2;
  let seated = false;
  let breathe = Math.random() * 10;
  const animate = (dt: number, speed: number) => {
    breathe += dt;
    if (seated) {
      torso.scale.y = 1 + Math.sin(breathe * 2) * 0.01;
      return;
    }
    const walking = speed > 0.05;
    if (walking) phase += dt * (speed / 0.75) * Math.PI;
    const amp = walking ? Math.min(0.55, 0.25 + speed * 0.12) : 0;
    const s = Math.sin(phase);
    legs[0].hip.rotation.x = s * amp;
    legs[1].hip.rotation.x = -s * amp;
    // Knees bend while the leg swings back and lifts.
    legs[0].knee.rotation.x = walking ? Math.max(0, -Math.cos(phase)) * amp * 1.3 : 0;
    legs[1].knee.rotation.x = walking ? Math.max(0, Math.cos(phase)) * amp * 1.3 : 0;
    arms[0].hip.rotation.x = -s * amp * 0.8;
    arms[1].hip.rotation.x = s * amp * 0.8;
    arms[0].knee.rotation.x = arms[1].knee.rotation.x = walking ? -0.25 : -0.05;
    body.position.y = walking ? Math.abs(Math.cos(phase)) * 0.04 : Math.sin(breathe * 2) * 0.005;
    head.rotation.y = walking ? 0 : Math.sin(breathe * 0.4) * 0.25;
  };
  const sit = () => {
    seated = true;
    body.position.set(0, -0.44, -0.1);
    for (const leg of legs) {
      leg.hip.rotation.x = -Math.PI / 2;
      leg.knee.rotation.x = Math.PI / 2;
    }
    arms[0].hip.rotation.x = arms[1].hip.rotation.x = -0.4;
    arms[0].knee.rotation.x = arms[1].knee.rotation.x = -0.6;
  };
  return { root, animate, sit };
}

// ----- signs and textures -----------------------------------------------------------------

function canvasTexture(w: number, h: number, draw: (ctx: CanvasRenderingContext2D) => void): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const ctx = c.getContext("2d");
  if (ctx) draw(ctx);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

export function textTexture(lines: string[], bg: string, fg: string, w = 256, h = 256): THREE.CanvasTexture {
  return canvasTexture(w, h, (ctx) => {
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, w, h);
    ctx.fillStyle = fg;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    const size = Math.floor(Math.min(h / (lines.length + 0.6), (w / Math.max(...lines.map((l) => l.length), 1)) * 1.6));
    ctx.font = `900 ${size}px "Arial Black", Impact, sans-serif`;
    lines.forEach((line, i) => ctx.fillText(line, w / 2, (h / (lines.length + 1)) * (i + 1)));
  });
}

/** Windows on a facade: one floor (3.5 m) per row, one window per 3 m. */
function facadeTexture(style: Building["style"], color: string): THREE.CanvasTexture {
  return canvasTexture(128, 128, (ctx) => {
    ctx.fillStyle = color;
    ctx.fillRect(0, 0, 128, 128);
    const glass = style === "glass" || style === "tower";
    // 4 floors x 4 windows per tile
    for (let r = 0; r < 4; r++) {
      for (let c = 0; c < 4; c++) {
        const lit = (r * 7 + c * 3) % 5 === 0;
        ctx.fillStyle = glass ? (lit ? "#cfe3f3" : "#5d7890") : lit ? "#f3e1a8" : "#2c3440";
        if (glass) ctx.fillRect(c * 32 + 2, r * 32 + 3, 28, 24);
        else ctx.fillRect(c * 32 + 9, r * 32 + 7, 14, 19);
      }
    }
    if (style === "brick") {
      ctx.fillStyle = "rgba(0,0,0,0.12)";
      for (let y = 0; y < 128; y += 4) ctx.fillRect(0, y, 128, 1);
    }
  });
}

const facadeCache = new Map<string, THREE.CanvasTexture>();
function facade(style: Building["style"], color: string): THREE.CanvasTexture {
  const key = `${style}|${color}`;
  let t = facadeCache.get(key);
  if (!t) {
    t = facadeTexture(style, color);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    facadeCache.set(key, t);
  }
  return t;
}

export function disposeTextures(): void {
  facadeCache.forEach((t) => t.dispose());
  facadeCache.clear();
}

// ----- buildings --------------------------------------------------------------------------

export function makeBuilding(b: Building): THREE.Group {
  const g = new THREE.Group();
  const w = b.x1 - b.x0;
  const d = b.z1 - b.z0;
  const special = b.style === "cafe" || b.style === "hotel" || b.style === "station";
  const style = special ? "stone" : b.style;
  // Each side gets its own texture repeat so windows keep their size.
  const side = (len: number) => {
    const t = facade(style, b.color).clone();
    t.needsUpdate = true;
    t.repeat.set(len / 12, b.height / 14);
    return new THREE.MeshStandardMaterial({ map: t, roughness: style === "glass" ? 0.3 : 0.85, metalness: style === "glass" ? 0.3 : 0 });
  };
  const roof = mat("#5b5f66");
  const materialsBySide = [side(d), side(d), roof, roof, side(w), side(w)];
  const box = new THREE.Mesh(new THREE.BoxGeometry(w, b.height, d), materialsBySide);
  box.castShadow = box.receiveShadow = true;
  box.position.set((b.x0 + b.x1) / 2, b.height / 2, (b.z0 + b.z1) / 2);
  g.add(box);
  // Ground floor: darker shop fronts
  const base = mesh(new THREE.BoxGeometry(w + 0.1, 3.2, d + 0.1), mat(style === "glass" || style === "tower" ? "#6b727c" : shade(b.color, -0.12)), false);
  base.position.set(box.position.x, 1.6, box.position.z);
  g.add(base);
  // Roof ledge
  const ledge = mesh(new THREE.BoxGeometry(w + 0.6, 0.6, d + 0.6), mat(shade(b.color, -0.15)));
  ledge.position.set(box.position.x, b.height, box.position.z);
  g.add(ledge);
  if (b.style === "cafe") g.add(cafeFront(b));
  if (b.style === "hotel") g.add(hotelFront(b));
  if (b.style === "station") g.add(stationFront(b));
  if (b.sign) g.add(sign(b));
  return g;
}

function shade(hex: string, amount: number): string {
  const c = new THREE.Color(hex);
  c.offsetHSL(0, 0, amount * 0.5);
  return `#${c.getHexString()}`;
}

function sign(b: Building): THREE.Mesh {
  const s = b.sign!;
  const w = Math.min(10, 1.4 * s.text.length + 2);
  const tex = textTexture([s.text], s.color, "#ffffff", 64 * Math.ceil(w), 96);
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, 1.4), new THREE.MeshStandardMaterial({ map: tex, emissive: "#ffffff", emissiveMap: tex, emissiveIntensity: 0.35 }));
  const cx = (b.x0 + b.x1) / 2;
  const cz = (b.z0 + b.z1) / 2;
  const y = 4.2;
  if (s.side === "n") m.position.set(cx, y, b.z0 - 0.08), (m.rotation.y = Math.PI);
  if (s.side === "s") m.position.set(cx, y, b.z1 + 0.08);
  if (s.side === "e") m.position.set(b.x1 + 0.08, y, cz), (m.rotation.y = Math.PI / 2);
  if (s.side === "w") m.position.set(b.x0 - 0.08, y, cz), (m.rotation.y = -Math.PI / 2);
  return m;
}

function cafeFront(b: Building): THREE.Group {
  const g = new THREE.Group();
  const w = b.x1 - b.x0;
  const cx = (b.x0 + b.x1) / 2;
  // Striped awning over the windows on the north side
  const tex = canvasTexture(64, 8, (ctx) => {
    for (let i = 0; i < 8; i++) {
      ctx.fillStyle = i % 2 ? "#ffffff" : "#1f7a4d";
      ctx.fillRect(i * 8, 0, 8, 8);
    }
  });
  tex.wrapS = THREE.RepeatWrapping;
  tex.repeat.set(w / 4, 1);
  const awning = new THREE.Mesh(new THREE.BoxGeometry(w - 1, 0.12, 2), new THREE.MeshStandardMaterial({ map: tex }));
  awning.rotation.x = -0.3;
  awning.position.set(cx, 3.1, b.z0 - 0.95);
  awning.castShadow = true;
  g.add(awning);
  const windows = mesh(new THREE.BoxGeometry(w - 2, 2.2, 0.1), mat("#9fc6d8", { rough: 0.15, metal: 0.2 }), false);
  windows.position.set(cx, 1.5, b.z0 - 0.06);
  g.add(windows);
  for (const x of [cx - 4, cx + 4]) {
    const table = makeTable();
    table.position.set(x, 0, b.z0 - 2.9);
    g.add(table);
  }
  return g;
}

function makeTable(): THREE.Group {
  const g = new THREE.Group();
  const top = mesh(new THREE.CylinderGeometry(0.4, 0.4, 0.04, 14), mat("#e8e2d6"));
  top.position.y = 0.75;
  const leg = mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.75, 6), mat("#333"));
  leg.position.y = 0.37;
  g.add(top, leg);
  return g;
}

function hotelFront(b: Building): THREE.Group {
  const g = new THREE.Group();
  const cz = (b.z0 + b.z1) / 2;
  const canopy = mesh(new THREE.BoxGeometry(3, 0.25, 6), mat("#7a1f2e"));
  canopy.position.set(b.x1 + 1.5, 3.2, cz);
  g.add(canopy);
  for (const dz of [-2.6, 2.6]) {
    const pole = mesh(new THREE.CylinderGeometry(0.05, 0.05, 3.2, 6), mat("#c9a646", { metal: 0.7, rough: 0.3 }));
    pole.position.set(b.x1 + 2.9, 1.6, cz + dz);
    g.add(pole);
  }
  const door = mesh(new THREE.BoxGeometry(0.1, 2.6, 2.4), mat("#2c2f36", { rough: 0.2 }), false);
  door.position.set(b.x1 + 0.05, 1.3, cz);
  g.add(door);
  return g;
}

function stationFront(b: Building): THREE.Group {
  const g = new THREE.Group();
  const cx = (b.x0 + b.x1) / 2;
  for (let i = -2; i <= 2; i++) {
    const col = mesh(new THREE.CylinderGeometry(0.5, 0.5, 14, 10), mat("#e6dcc4"));
    col.position.set(cx + i * 6, 7, b.z0 - 0.6);
    g.add(col);
  }
  const win = mesh(new THREE.CircleGeometry(4, 20, 0, Math.PI), mat("#7fa3b8", { rough: 0.2, metal: 0.3 }), false);
  win.position.set(cx, 9, b.z0 - 0.05);
  win.rotation.y = Math.PI;
  g.add(win);
  return g;
}

export function makeBillboard(bb: Billboard): THREE.Mesh {
  const tex = textTexture(bb.lines, bb.bg, bb.fg, 256, Math.round((256 * bb.h) / bb.w));
  const m = new THREE.Mesh(
    new THREE.PlaneGeometry(bb.w, bb.h),
    new THREE.MeshStandardMaterial({ map: tex, emissive: "#ffffff", emissiveMap: tex, emissiveIntensity: 0.9 }),
  );
  m.position.set(bb.x, bb.y, bb.z);
  m.rotation.y = bb.rot;
  return m;
}

// ----- props ------------------------------------------------------------------------------

export function makeTree(): THREE.Group {
  const g = new THREE.Group();
  const trunk = mesh(new THREE.CylinderGeometry(0.18, 0.28, 2.4, 7), mat("#6b4a2e"));
  trunk.position.y = 1.2;
  g.add(trunk);
  const leaves = mat(Math.random() < 0.5 ? "#3f8f3a" : "#4f9d45", { rough: 0.9 });
  for (const [x, y, z, r] of [
    [0, 3.4, 0, 1.7],
    [0.8, 2.9, 0.3, 1.1],
    [-0.7, 3, -0.4, 1.2],
  ]) {
    const blob = mesh(new THREE.IcosahedronGeometry(r, 0), leaves);
    blob.position.set(x, y, z);
    g.add(blob);
  }
  g.scale.setScalar(0.85 + Math.random() * 0.5);
  return g;
}

export function makeTaxi(color: string): THREE.Group {
  const g = new THREE.Group();
  const paint = mat(color, { rough: 0.45 });
  const bodyMesh = mesh(new THREE.BoxGeometry(1.8, 0.7, 4.4), paint);
  bodyMesh.position.y = 0.65;
  g.add(bodyMesh);
  const cabin = mesh(new THREE.BoxGeometry(1.6, 0.55, 2.2), mat("#26313b", { rough: 0.15, metal: 0.4 }));
  cabin.position.set(0, 1.27, -0.2);
  g.add(cabin);
  const roof = mesh(new THREE.BoxGeometry(1.62, 0.06, 2), paint);
  roof.position.set(0, 1.57, -0.2);
  g.add(roof);
  if (color === "#f7c513") {
    const light = mesh(new THREE.BoxGeometry(0.7, 0.22, 0.3), mat("#ffffff", { emissive: "#fff5c0" }));
    light.position.set(0, 1.72, -0.2);
    g.add(light);
  }
  const tire = mat("#151515");
  for (const [x, z] of [
    [-0.85, 1.4],
    [0.85, 1.4],
    [-0.85, -1.4],
    [0.85, -1.4],
  ]) {
    const w = mesh(new THREE.CylinderGeometry(0.34, 0.34, 0.25, 12), tire);
    w.rotation.z = Math.PI / 2;
    w.position.set(x, 0.34, z);
    g.add(w);
  }
  for (const x of [-0.6, 0.6]) {
    const head = mesh(new THREE.BoxGeometry(0.35, 0.15, 0.05), mat("#fffbe0", { emissive: "#fff7c2" }), false);
    head.position.set(x, 0.75, 2.21);
    const tail = mesh(new THREE.BoxGeometry(0.35, 0.15, 0.05), mat("#c0262d", { emissive: "#8a0d12" }), false);
    tail.position.set(x, 0.75, -2.21);
    g.add(head, tail);
  }
  return g;
}

export function makeProp(p: Prop): THREE.Group {
  const g = new THREE.Group();
  if (p.kind === "cart") {
    const box = mesh(new THREE.BoxGeometry(2.2, 1, 1.2), mat("#d8d8d8", { metal: 0.6, rough: 0.35 }));
    box.position.y = 0.9;
    g.add(box);
    const umbrella = mesh(new THREE.ConeGeometry(1.7, 0.6, 10), mat("#e8402e"));
    umbrella.position.y = 2.6;
    const pole = mesh(new THREE.CylinderGeometry(0.03, 0.03, 2.2, 6), mat("#888"));
    pole.position.y = 1.4;
    const label = new THREE.Mesh(new THREE.PlaneGeometry(1.8, 0.45), new THREE.MeshStandardMaterial({ map: textTexture(["HOT DOGS"], "#ffcc33", "#b0272d", 256, 64) }));
    label.position.set(0, 1.05, -0.61);
    label.rotation.y = Math.PI;
    for (const x of [-0.8, 0.8]) {
      const wheel = mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.1, 12), mat("#222"));
      wheel.rotation.x = Math.PI / 2;
      wheel.rotation.z = Math.PI / 2;
      wheel.position.set(x, 0.3, 0.62);
      g.add(wheel);
    }
    g.add(umbrella, pole, label);
  }
  if (p.kind === "bench") {
    const wood = mat("#7a5532");
    const seat = mesh(new THREE.BoxGeometry(2, 0.08, 0.5), wood);
    seat.position.set(0, 0.46, 0);
    const back = mesh(new THREE.BoxGeometry(2, 0.45, 0.06), wood);
    back.position.set(0, 0.75, -0.25);
    back.rotation.x = -0.15;
    g.add(seat, back);
    for (const x of [-0.85, 0.85]) {
      const leg = mesh(new THREE.BoxGeometry(0.08, 0.46, 0.5), mat("#2c2c2c"));
      leg.position.set(x, 0.23, 0);
      g.add(leg);
    }
  }
  if (p.kind === "lamp") {
    const pole = mesh(new THREE.CylinderGeometry(0.08, 0.12, 6, 8), mat("#2f3a33", { metal: 0.5 }));
    pole.position.y = 3;
    const arm = mesh(new THREE.BoxGeometry(0.1, 0.1, 1.4), mat("#2f3a33"));
    arm.position.set(0, 5.9, 0.6);
    const bulb = mesh(new THREE.BoxGeometry(0.4, 0.15, 0.6), mat("#fff3c4", { emissive: "#ffe08a" }), false);
    bulb.position.set(0, 5.8, 1.2);
    g.add(pole, arm, bulb);
  }
  if (p.kind === "subway") {
    const rail = mat("#2f5d3a", { metal: 0.4 });
    for (const x of [-1.6, 1.6]) {
      const side = mesh(new THREE.BoxGeometry(0.08, 1, 2.4), rail);
      side.position.set(x, 0.5, 0);
      g.add(side);
      const globe = mesh(new THREE.SphereGeometry(0.22, 12, 8), mat("#7be07b", { emissive: "#3fbf3f" }), false);
      globe.position.set(x, 1.35, 1.1);
      g.add(globe);
    }
    const back = mesh(new THREE.BoxGeometry(3.2, 1, 0.08), rail);
    back.position.set(0, 0.5, -1.2);
    const stairs = mesh(new THREE.BoxGeometry(3, 0.05, 2.3), mat("#1c1c1c"), false);
    stairs.position.y = 0.03;
    const label = new THREE.Mesh(new THREE.PlaneGeometry(2.6, 0.5), new THREE.MeshStandardMaterial({ map: textTexture(["SUBWAY  N Q R"], "#111111", "#ffffff", 512, 96) }));
    label.position.set(0, 1.25, -1.15);
    g.add(back, stairs, label);
  }
  if (p.kind === "hydrant") {
    const h = mesh(new THREE.CylinderGeometry(0.15, 0.18, 0.7, 8), mat("#c0262d"));
    h.position.y = 0.35;
    const top = mesh(new THREE.SphereGeometry(0.16, 8, 6), mat("#c0262d"));
    top.position.y = 0.7;
    g.add(h, top);
  }
  if (p.kind === "easel") {
    const wood = mat("#8a6a44");
    for (const x of [-0.3, 0.3]) {
      const leg = mesh(new THREE.BoxGeometry(0.05, 1.6, 0.05), wood);
      leg.position.set(x, 0.8, 0);
      leg.rotation.z = x > 0 ? -0.12 : 0.12;
      g.add(leg);
    }
    const canvasTex = canvasTexture(64, 48, (ctx) => {
      ctx.fillStyle = "#9fd0f0";
      ctx.fillRect(0, 0, 64, 48);
      ctx.fillStyle = "#4f9d45";
      ctx.fillRect(0, 30, 64, 18);
      ctx.fillStyle = "#3b4250";
      for (let i = 0; i < 6; i++) ctx.fillRect(4 + i * 10, 12 + (i % 3) * 5, 7, 20);
    });
    const art = new THREE.Mesh(new THREE.BoxGeometry(0.9, 0.7, 0.04), [mat("#eee"), mat("#eee"), mat("#eee"), mat("#eee"), new THREE.MeshStandardMaterial({ map: canvasTex }), mat("#eee")]);
    art.position.set(0, 1.35, 0.05);
    art.castShadow = true;
    g.add(art);
  }
  g.position.set(p.x, 0, p.z);
  g.rotation.y = p.rot;
  return g;
}

export type MarkerKind = "todo" | "done" | "chat";

/** A floating marker: "!" over missions, "✓" once done, a speech bubble over people to chat with. */
export function makeMarker(kind: MarkerKind): THREE.Sprite {
  const tex = canvasTexture(64, 64, (ctx) => {
    ctx.fillStyle = kind === "done" ? "#2fbf71" : kind === "todo" ? "#ffcc33" : "#ffffff";
    ctx.lineWidth = 4;
    ctx.strokeStyle = "#14181e";
    ctx.beginPath();
    if (kind === "chat") {
      ctx.ellipse(32, 28, 27, 20, 0, 0, Math.PI * 2);
      ctx.moveTo(20, 44);
      ctx.lineTo(14, 60);
      ctx.lineTo(32, 47);
    } else {
      ctx.arc(32, 32, 28, 0, Math.PI * 2);
    }
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#14181e";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    if (kind === "chat") {
      for (const x of [20, 32, 44]) {
        ctx.beginPath();
        ctx.arc(x, 28, 4, 0, Math.PI * 2);
        ctx.fill();
      }
    } else {
      ctx.font = "900 40px Arial, sans-serif";
      ctx.fillText(kind === "done" ? "✓" : "!", 32, 35);
    }
  });
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false }));
  s.scale.set(0.55, 0.55, 1);
  s.renderOrder = 10;
  return s;
}
