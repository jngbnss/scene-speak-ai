/**
 * The 3D street: builds the three.js scene from layout.ts and runs the game loop
 * (player movement, walkers, traffic, third-person camera). React only feeds it input.
 */
import * as THREE from "three";

import {
  AVENUES,
  BLOCKS,
  PARK_EDGE,
  PARK_PATHS,
  PEOPLE,
  PLAYER_START,
  POND,
  PROPS,
  ROAD_HALF,
  SIDEWALK,
  STREETS,
  TALK_DISTANCE,
  WORLD,
  buildBillboards,
  buildBuildings,
  buildColliders,
  buildTrees,
  buildWalkers,
  moveCircle,
  routeLength,
  routePoint,
  type Look,
  type Person,
  type Point,
  type Rect,
} from "./layout";
import {
  disposeShared,
  disposeTextures,
  makeBillboard,
  makeBuilding,
  makeMarker,
  makePerson,
  makeProp,
  makeTaxi,
  makeTree,
  mat,
  type MarkerKind,
  type PersonRig,
} from "./models";
import { carPosition, isGreen, spawnCars, stepCars, type Car } from "./traffic";

export interface Input {
  /** -1..1 each: forward/back and right/left, relative to the camera. */
  forward: number;
  strafe: number;
  run: boolean;
  /** Camera turn from keys, -1..1. */
  turn: number;
}

export interface CityCallbacks {
  onNearby: (person: Person | null) => void;
}

const WALK = 4.2;
const RUN = 8;
const RADIUS = 0.35;
const CAM_MIN = 3.5;
const CAM_MAX = 16;

interface Actor {
  person?: Person;
  look: Look;
  rig: PersonRig;
  route?: Point[];
  routeLen: number;
  dist: number;
  speed: number;
  /** Sideways step to get around someone in the way, smoothed. */
  dodge: number;
  pos: Point;
  heading: number;
  marker?: THREE.Sprite;
  markerKind?: MarkerKind;
}

export class City {
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera = new THREE.PerspectiveCamera(60, 1, 0.3, 600);
  private sun = new THREE.DirectionalLight("#fff4e0", 2.6);
  private player: PersonRig;
  private pos: Point = { x: PLAYER_START.x, z: PLAYER_START.z };
  private heading = PLAYER_START.facing;
  private yaw = PLAYER_START.facing + Math.PI; // camera sits behind the player
  private pitch = 0.32;
  private camDist = 7.5;
  private actors: Actor[] = [];
  private cars: { car: Car; mesh: THREE.Group }[] = [];
  private solids: Rect[];
  private walls: THREE.Object3D[] = [];
  // Not shared: their colors change with the lights.
  private lampMats = {
    avenue: new THREE.MeshStandardMaterial({ color: "#2fbf71", emissive: "#2fbf71" }),
    street: new THREE.MeshStandardMaterial({ color: "#d93030", emissive: "#d93030" }),
  };
  private raycaster = new THREE.Raycaster();
  private frame = 0;
  private last = 0;
  private time = 0;
  private nearby: Person | null = null;
  private running = false;
  private cleared: ReadonlySet<string> = new Set();
  private drag: { id: number; x: number; y: number } | null = null;

  input: Input = { forward: 0, strafe: 0, run: false, turn: 0 };

  constructor(
    private canvas: HTMLCanvasElement,
    private label: HTMLElement | null,
    private callbacks: CityCallbacks,
  ) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    this.scene.background = new THREE.Color("#a9d6f5");
    this.scene.fog = new THREE.Fog("#c4e0f2", 90, 260);
    this.scene.add(new THREE.HemisphereLight("#e2f0ff", "#a39a88", 2.3));
    this.sun.position.set(40, 80, 30);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    const sc = this.sun.shadow.camera;
    sc.left = sc.bottom = -45;
    sc.right = sc.top = 45;
    sc.near = 10;
    sc.far = 220;
    this.sun.shadow.bias = -0.0005;
    this.scene.add(this.sun, this.sun.target);

    const buildings = buildBuildings();
    const trees = buildTrees();
    this.solids = buildColliders(buildings, trees);
    this.buildGround();
    for (const b of buildings) {
      const g = makeBuilding(b);
      this.scene.add(g);
      this.walls.push(g.children[0]);
    }
    for (const bb of buildBillboards()) this.scene.add(makeBillboard(bb));
    for (const t of trees) {
      const tree = makeTree();
      tree.position.set(t.x, 0, t.z);
      this.scene.add(tree);
    }
    for (const p of PROPS) this.scene.add(makeProp(p));
    this.buildTrafficLights();

    for (const person of PEOPLE) this.addActor(person.look, person);
    for (const w of buildWalkers()) {
      this.addActor(w.look, undefined, w.route, w.speed, w.offset);
    }
    for (const car of spawnCars(2)) {
      const mesh = makeTaxi(car.color);
      this.scene.add(mesh);
      this.cars.push({ car, mesh });
    }

    this.player = makePerson({ skin: "#f1c7a5", hair: "#1d1a1f", shirt: "#2f6fd6", pants: "#2b2f3a", shoes: "#f4f4f4" });
    this.scene.add(this.player.root);

    canvas.addEventListener("pointerdown", this.onPointerDown);
    canvas.addEventListener("pointermove", this.onPointerMove);
    canvas.addEventListener("pointerup", this.onPointerUp);
    canvas.addEventListener("pointercancel", this.onPointerUp);
    canvas.addEventListener("wheel", this.onWheel, { passive: false });
    this.resize();
    this.update(0);
    this.render();
  }

  // ----- setup ----------------------------------------------------------------------------

  private flat(rect: Rect, y: number, material: THREE.Material, shadow = true): THREE.Mesh {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(rect.x1 - rect.x0, rect.z1 - rect.z0), material);
    m.rotation.x = -Math.PI / 2;
    m.position.set((rect.x0 + rect.x1) / 2, y, (rect.z0 + rect.z1) / 2);
    m.receiveShadow = shadow;
    this.scene.add(m);
    return m;
  }

  private buildGround(): void {
    const pad = 200;
    // Sidewalk everywhere south of the park, grass beyond the city
    this.flat({ x0: WORLD.x0 - pad, x1: WORLD.x1 + pad, z0: WORLD.z0 - pad, z1: WORLD.z1 + pad }, -0.02, mat("#7da35a"));
    this.flat({ x0: WORLD.x0, x1: WORLD.x1, z0: PARK_EDGE, z1: WORLD.z1 }, 0, mat("#b9b5ad", { rough: 0.95 }));
    // Park
    this.flat({ x0: WORLD.x0, x1: WORLD.x1, z0: WORLD.z0, z1: PARK_EDGE }, 0.02, mat("#5f9e4a", { rough: 1 }));
    for (const p of PARK_PATHS) this.flat(p, 0.04, mat("#d9c9a3", { rough: 1 }));
    this.flat(POND, 0.06, mat("#3f7fb5", { rough: 0.1, metal: 0.2 }));
    // Low stone wall along the park, with gaps for the paths
    const wall = mat("#8d8577");
    for (let x = WORLD.x0; x < WORLD.x1; x += 10) {
      if (PARK_PATHS.some((p) => p.x0 < x + 10 && p.x1 > x && p.z1 >= PARK_EDGE)) continue;
      const w = new THREE.Mesh(new THREE.BoxGeometry(10, 0.6, 0.5), wall);
      w.position.set(x + 5, 0.3, PARK_EDGE - 0.25);
      w.castShadow = w.receiveShadow = true;
      this.scene.add(w);
      this.solids.push({ x0: x, x1: x + 10, z0: PARK_EDGE - 0.5, z1: PARK_EDGE });
    }

    // Roads
    const asphalt = mat("#5a5e64", { rough: 0.95 });
    const line = mat("#e8e2c8", { rough: 0.9 });
    const yellow = mat("#e6b422", { rough: 0.9 });
    for (const s of STREETS) {
      this.flat({ x0: WORLD.x0, x1: WORLD.x1, z0: s.z - ROAD_HALF, z1: s.z + ROAD_HALF }, 0.02, asphalt);
      this.flat({ x0: WORLD.x0, x1: WORLD.x1, z0: s.z - 0.08, z1: s.z + 0.08 }, 0.04, yellow, false);
    }
    for (const a of AVENUES) {
      this.flat({ x0: a.x - ROAD_HALF, x1: a.x + ROAD_HALF, z0: STREETS[0].z - ROAD_HALF, z1: WORLD.z1 }, 0.02, asphalt);
      for (let z = STREETS[0].z + ROAD_HALF + 2; z < WORLD.z1; z += 6) {
        if (STREETS.some((s) => Math.abs(z - s.z) < ROAD_HALF + 4)) continue;
        this.flat({ x0: a.x - 0.08, x1: a.x + 0.08, z0: z, z1: z + 3 }, 0.04, line, false);
      }
    }
    // Crosswalks at every crossing
    const stripes = new THREE.CanvasTexture(stripeCanvas());
    stripes.wrapS = stripes.wrapT = THREE.RepeatWrapping;
    for (const a of AVENUES) {
      for (const s of STREETS) {
        const off = ROAD_HALF + 1.6;
        // across the avenue (north and south of the street; the avenue starts at 59th St)
        for (const dz of [-off, off]) {
          if (s === STREETS[0] && dz < 0) continue;
          const t = stripes.clone();
          t.needsUpdate = true;
          t.repeat.set(ROAD_HALF, 1);
          this.flat({ x0: a.x - ROAD_HALF, x1: a.x + ROAD_HALF, z0: s.z + dz - 1.4, z1: s.z + dz + 1.4 }, 0.045, new THREE.MeshStandardMaterial({ map: t, transparent: true }), false);
        }
        // across the street (west and east of the avenue)
        for (const dx of [-off, off]) {
          const t = stripes.clone();
          t.needsUpdate = true;
          t.repeat.set(ROAD_HALF, 1);
          const m = this.flat({ x0: a.x + dx - 1.4, x1: a.x + dx + 1.4, z0: s.z - ROAD_HALF, z1: s.z + ROAD_HALF }, 0.045, new THREE.MeshStandardMaterial({ map: t, transparent: true }), false);
          m.geometry.dispose();
          m.geometry = new THREE.PlaneGeometry(2 * ROAD_HALF, 2.8);
          m.rotation.z = Math.PI / 2;
        }
      }
    }
    // Curbs around every block's sidewalk
    const curb = mat("#d0ccc4");
    for (const row of BLOCKS) {
      for (const b of row) {
        const r = { x0: b.x0 - SIDEWALK, x1: b.x1 + SIDEWALK, z0: b.z0 - SIDEWALK, z1: b.z1 + SIDEWALK };
        this.flat(r, 0.03, mat("#c4c0b8", { rough: 0.95 }));
        for (const edge of [
          { x0: r.x0, x1: r.x1, z0: r.z0 - 0.15, z1: r.z0 },
          { x0: r.x0, x1: r.x1, z0: r.z1, z1: r.z1 + 0.15 },
          { x0: r.x0 - 0.15, x1: r.x0, z0: r.z0, z1: r.z1 },
          { x0: r.x1, x1: r.x1 + 0.15, z0: r.z0, z1: r.z1 },
        ]) {
          this.flat(edge, 0.06, curb, false);
        }
      }
    }
  }

  private buildTrafficLights(): void {
    const pole = mat("#25292e", { metal: 0.5 });
    for (const a of AVENUES) {
      for (const s of STREETS) {
        for (const [dx, dz] of [
          [-1, -1],
          [1, 1],
        ]) {
          const x = a.x + dx * (ROAD_HALF + 0.8);
          const z = s.z + dz * (ROAD_HALF + 0.8);
          const g = new THREE.Group();
          const p = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.12, 4.2, 8), pole);
          p.position.y = 2.1;
          p.castShadow = true;
          g.add(p);
          // One lamp facing the avenue traffic, one facing the street traffic
          const forAvenue = new THREE.Mesh(new THREE.SphereGeometry(0.2, 10, 8), this.lampMats.avenue);
          forAvenue.position.set(0, 3.9, dz * 0.25);
          const forStreet = new THREE.Mesh(new THREE.SphereGeometry(0.2, 10, 8), this.lampMats.street);
          forStreet.position.set(dx * 0.25, 3.5, 0);
          const box = new THREE.Mesh(new THREE.BoxGeometry(0.45, 1.1, 0.45), pole);
          box.position.y = 3.7;
          g.add(box, forAvenue, forStreet);
          g.position.set(x, 0, z);
          this.scene.add(g);
          this.solids.push({ x0: x - 0.15, x1: x + 0.15, z0: z - 0.15, z1: z + 0.15 });
        }
      }
    }
  }

  private addActor(look: Look, person?: Person, route?: Point[], speed = 1.3, offset = 0): void {
    const rig = makePerson(look);
    const actualRoute = person?.route ?? route;
    const routeLen = actualRoute ? routeLength(actualRoute) : 0;
    const spot = person?.spot;
    const actor: Actor = {
      person,
      look,
      rig,
      route: actualRoute,
      routeLen,
      dist: routeLen * (person?.offset ?? offset),
      speed: person?.speed ?? speed,
      dodge: 0,
      pos: spot ? { x: spot.x, z: spot.z } : { x: 0, z: 0 },
      heading: spot?.facing ?? 0,
    };
    if (spot?.sit) rig.sit();
    if (person) {
      actor.markerKind = person.kind === "mission" ? "todo" : "chat";
      actor.marker = makeMarker(actor.markerKind);
      this.scene.add(actor.marker);
    }
    this.scene.add(rig.root);
    this.actors.push(actor);
  }

  // ----- public ---------------------------------------------------------------------------

  setCleared(cleared: ReadonlySet<string>): void {
    this.cleared = cleared;
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    this.last = performance.now();
    const tick = (now: number) => {
      if (!this.running) return;
      const dt = Math.min(0.05, (now - this.last) / 1000);
      this.last = now;
      this.update(dt);
      this.render();
      this.frame = requestAnimationFrame(tick);
    };
    this.frame = requestAnimationFrame(tick);
  }

  stop(): void {
    this.running = false;
    cancelAnimationFrame(this.frame);
    this.input = { forward: 0, strafe: 0, run: false, turn: 0 };
    this.drag = null;
  }

  resize(): void {
    const w = this.canvas.clientWidth || 1;
    const h = this.canvas.clientHeight || 1;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    if (!this.running) this.render();
  }

  dispose(): void {
    this.stop();
    const c = this.canvas;
    c.removeEventListener("pointerdown", this.onPointerDown);
    c.removeEventListener("pointermove", this.onPointerMove);
    c.removeEventListener("pointerup", this.onPointerUp);
    c.removeEventListener("pointercancel", this.onPointerUp);
    c.removeEventListener("wheel", this.onWheel);
    this.scene.traverse((o) => {
      if (o instanceof THREE.Mesh || o instanceof THREE.Sprite) {
        o.geometry.dispose();
        const ms = Array.isArray(o.material) ? o.material : [o.material];
        for (const m of ms) {
          (m as THREE.MeshStandardMaterial).map?.dispose();
          m.dispose();
        }
      }
    });
    disposeShared();
    disposeTextures();
    this.renderer.dispose();
  }

  /** Who the player would talk to right now. */
  get target(): Person | null {
    return this.nearby;
  }

  // ----- camera input ---------------------------------------------------------------------

  private onPointerDown = (e: PointerEvent) => {
    this.drag = { id: e.pointerId, x: e.clientX, y: e.clientY };
    this.canvas.setPointerCapture(e.pointerId);
  };

  private onPointerMove = (e: PointerEvent) => {
    if (!this.drag || this.drag.id !== e.pointerId) return;
    const dx = e.clientX - this.drag.x;
    const dy = e.clientY - this.drag.y;
    this.drag.x = e.clientX;
    this.drag.y = e.clientY;
    this.yaw -= dx * 0.006;
    this.pitch = clamp(this.pitch + dy * 0.004, 0.05, 1.2);
  };

  private onPointerUp = (e: PointerEvent) => {
    if (this.drag?.id === e.pointerId) this.drag = null;
  };

  private onWheel = (e: WheelEvent) => {
    e.preventDefault();
    this.camDist = clamp(this.camDist * (1 + Math.sign(e.deltaY) * 0.1), CAM_MIN, CAM_MAX);
  };

  // ----- simulation -----------------------------------------------------------------------

  private update(dt: number): void {
    this.time += dt;
    const t = this.time;
    this.yaw -= this.input.turn * dt * 2;

    // Player: move relative to where the camera looks
    const fx = -Math.sin(this.yaw);
    const fz = -Math.cos(this.yaw);
    let mx = fx * this.input.forward - fz * this.input.strafe;
    let mz = fz * this.input.forward + fx * this.input.strafe;
    const len = Math.hypot(mx, mz);
    let speed = 0;
    if (len > 0.05) {
      mx /= Math.max(1, len);
      mz /= Math.max(1, len);
      speed = (this.input.run ? RUN : WALK) * Math.min(1, len);
      const dynamic: Rect[] = this.actors.map((a) => box(a.pos, 0.3));
      for (const { car } of this.cars) {
        const p = carPosition(car);
        const along = Math.abs(Math.sin(p.heading)) > 0.5;
        dynamic.push(along ? { x0: p.x - 2.2, x1: p.x + 2.2, z0: p.z - 0.9, z1: p.z + 0.9 } : { x0: p.x - 0.9, x1: p.x + 0.9, z0: p.z - 2.2, z1: p.z + 2.2 });
      }
      this.pos = moveCircle(this.pos, (mx / Math.hypot(mx, mz)) * speed * dt, (mz / Math.hypot(mx, mz)) * speed * dt, RADIUS, [...this.solids, ...dynamic]);
      this.heading = turnTowards(this.heading, Math.atan2(mx, mz), dt * 10);
    }
    this.player.root.position.set(this.pos.x, 0, this.pos.z);
    this.player.root.rotation.y = this.heading;
    this.player.animate(dt, speed);

    // Who is close enough to talk to
    let best: Actor | null = null;
    let bestD = TALK_DISTANCE;
    for (const a of this.actors) {
      if (!a.person) continue;
      const d = Math.hypot(a.pos.x - this.pos.x, a.pos.z - this.pos.z);
      if (d < bestD) {
        best = a;
        bestD = d;
      }
    }
    const near = best?.person ?? null;
    if (near !== this.nearby) {
      this.nearby = near;
      this.callbacks.onNearby(near);
    }

    // People
    for (const a of this.actors) {
      let moving = 0;
      if (a.route) {
        const stopForPlayer = a === best || (a.person && Math.hypot(a.pos.x - this.pos.x, a.pos.z - this.pos.z) < 1.2);
        if (!stopForPlayer) {
          a.dist += a.speed * dt;
          moving = a.speed;
        }
        const p = routePoint(a.route, a.dist);
        // Step aside for the player and for people standing on the sidewalk.
        const sideX = Math.cos(p.heading);
        const sideZ = -Math.sin(p.heading);
        let want = 0;
        for (const o of [this.pos, ...this.actors.filter((b) => !b.route).map((b) => b.pos)]) {
          const ox = o.x - p.x;
          const oz = o.z - p.z;
          const ahead = ox * Math.sin(p.heading) + oz * Math.cos(p.heading);
          const side = ox * sideX + oz * sideZ;
          if (ahead > -0.5 && ahead < 2.5 && Math.abs(side) < 1.1) want = side > 0 ? -1.2 : 1.2;
        }
        a.dodge += (want - a.dodge) * Math.min(1, dt * 3);
        a.pos = { x: p.x + sideX * a.dodge, z: p.z + sideZ * a.dodge };
        a.heading = stopForPlayer ? turnTowards(a.heading, Math.atan2(this.pos.x - a.pos.x, this.pos.z - a.pos.z), dt * 6) : turnTowards(a.heading, p.heading, dt * 8);
      } else if (a === best && !a.person?.spot?.sit) {
        a.heading = turnTowards(a.heading, Math.atan2(this.pos.x - a.pos.x, this.pos.z - a.pos.z), dt * 5);
      } else if (a.person?.spot) {
        a.heading = turnTowards(a.heading, a.person.spot.facing, dt * 2);
      }
      a.rig.root.position.set(a.pos.x, 0, a.pos.z);
      a.rig.root.rotation.y = a.heading;
      a.rig.animate(dt, moving);
      if (a.marker && a.person) {
        const kind: MarkerKind = a.person.kind === "chat" ? "chat" : this.cleared.has(a.person.sceneId) ? "done" : "todo";
        if (kind !== a.markerKind) {
          a.marker.material.map?.dispose();
          a.marker.material.dispose();
          const next = makeMarker(kind);
          a.marker.material = next.material;
          a.markerKind = kind;
        }
        const d = Math.hypot(a.pos.x - this.pos.x, a.pos.z - this.pos.z);
        a.marker.visible = kind !== "chat" || d < 22;
        const h = (a.look.height ?? 1) * (a.person.spot?.sit ? 1.45 : 1.95);
        a.marker.position.set(a.pos.x, h + 0.25 + Math.sin(t * 2.5 + a.pos.x) * 0.06, a.pos.z);
        const s = kind === "chat" ? 0.45 : 0.6 + Math.min(1.2, d / 40);
        a.marker.scale.set(s, s, 1);
      }
    }

    // Traffic
    stepCars(
      this.cars.map((c) => c.car),
      dt,
      t,
      this.pos,
    );
    for (const { car, mesh } of this.cars) {
      const p = carPosition(car);
      mesh.position.set(p.x, 0, p.z);
      mesh.rotation.y = p.heading;
    }
    this.lampMats.avenue.color.set(isGreen("z", t) ? "#2fbf71" : "#d93030");
    this.lampMats.avenue.emissive.copy(this.lampMats.avenue.color);
    this.lampMats.street.color.set(isGreen("x", t) ? "#2fbf71" : "#d93030");
    this.lampMats.street.emissive.copy(this.lampMats.street.color);

    // Camera: behind and above the player, pulled in when a building is in the way
    const head = new THREE.Vector3(this.pos.x, 1.6, this.pos.z);
    const dir = new THREE.Vector3(Math.sin(this.yaw) * Math.cos(this.pitch), Math.sin(this.pitch), Math.cos(this.yaw) * Math.cos(this.pitch));
    let dist = this.camDist;
    this.raycaster.set(head, dir);
    this.raycaster.far = dist;
    const hit = this.raycaster.intersectObjects(this.walls, false)[0];
    if (hit) dist = Math.max(1.2, hit.distance - 0.4);
    this.camera.position.copy(head).addScaledVector(dir, dist);
    this.camera.lookAt(head);

    this.sun.position.set(this.pos.x + 40, 80, this.pos.z + 30);
    this.sun.target.position.set(this.pos.x, 0, this.pos.z);

    this.placeLabel(best);
  }

  private placeLabel(best: Actor | null): void {
    if (!this.label) return;
    if (!best?.person) {
      this.label.hidden = true;
      return;
    }
    const v = new THREE.Vector3(best.pos.x, (best.look.height ?? 1) * (best.person.spot?.sit ? 1.45 : 1.95) + 0.75, best.pos.z).project(this.camera);
    const w = this.canvas.clientWidth;
    const h = this.canvas.clientHeight;
    this.label.hidden = v.z > 1;
    this.label.style.transform = `translate(-50%, -100%) translate(${((v.x + 1) / 2) * w}px, ${((1 - v.y) / 2) * h}px)`;
    this.label.textContent = `${best.person.name} · ${best.person.roleKo}`;
  }

  private render(): void {
    this.renderer.render(this.scene, this.camera);
  }
}

function box(p: Point, r: number): Rect {
  return { x0: p.x - r, x1: p.x + r, z0: p.z - r, z1: p.z + r };
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function turnTowards(from: number, to: number, step: number): number {
  let d = to - from;
  d = Math.atan2(Math.sin(d), Math.cos(d));
  return Math.abs(d) <= step ? to : from + Math.sign(d) * step;
}

function stripeCanvas(): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = 32;
  c.height = 8;
  const ctx = c.getContext("2d");
  if (ctx) {
    ctx.fillStyle = "rgba(240,240,232,0.95)";
    ctx.fillRect(0, 0, 18, 8);
  }
  return c;
}
