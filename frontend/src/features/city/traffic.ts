/** Taxis on fixed lanes with traffic lights. Cars stop for red lights, the car ahead and the player. */
import { AVENUES, LANES, ROAD_HALF, STREETS, type Lane, type Point } from "./layout";

export interface Car {
  lane: number;
  /** Position along the lane's axis. */
  s: number;
  speed: number;
  color: string;
}

export const CRUISE = 9; // m/s, about 32 km/h
const ACCEL = 5;
const BRAKE = 12;
const GAP = 8; // keep this far behind the car ahead
const CAR_HALF = 2.2;
// One cycle: avenues green, all red, streets green, all red.
export const CYCLE = 28;

/** Is it green for traffic moving along this axis ("z" = avenues, "x" = streets)? */
export function isGreen(axis: Lane["axis"], t: number): boolean {
  const c = ((t % CYCLE) + CYCLE) % CYCLE;
  return axis === "z" ? c < 12 : c >= 14 && c < 26;
}

export function carPosition(car: Car): Point & { heading: number } {
  const lane = LANES[car.lane];
  const heading = lane.axis === "z" ? (lane.dir > 0 ? 0 : Math.PI) : lane.dir > 0 ? Math.PI / 2 : -Math.PI / 2;
  return lane.axis === "z" ? { x: lane.at, z: car.s, heading } : { x: car.s, z: lane.at, heading };
}

/** Stop lines the car will meet on its lane, in the order it reaches them. */
function stopLines(lane: Lane): number[] {
  const crossings = lane.axis === "z" ? STREETS.map((s) => s.z) : AVENUES.map((a) => a.x);
  return crossings.map((c) => c - lane.dir * (ROAD_HALF + 1.5));
}

export function spawnCars(perLane = 2): Car[] {
  const colors = ["#f7c513", "#f7c513", "#f7c513", "#e8e8e8", "#2b2f3a", "#b0272d"];
  const cars: Car[] = [];
  LANES.forEach((lane, i) => {
    const len = Math.abs(lane.to - lane.from);
    for (let k = 0; k < perLane; k++) {
      const s0 = lane.dir > 0 ? lane.from : lane.to;
      cars.push({
        lane: i,
        s: s0 + lane.dir * ((len * (k + 0.3 + (i % 3) * 0.1)) / perLane),
        speed: CRUISE,
        color: colors[(i + k) % colors.length],
      });
    }
  });
  return cars;
}

/** Advance every car by dt seconds at time t. */
export function stepCars(cars: Car[], dt: number, t: number, player: Point | null): void {
  for (const car of cars) {
    const lane = LANES[car.lane];
    const ahead = (s: number) => (s - car.s) * lane.dir; // > 0 when s is in front of the car
    let limit = Infinity; // how far the car may go before it must stop

    if (!isGreen(lane.axis, t)) {
      for (const line of stopLines(lane)) {
        const d = ahead(line) - CAR_HALF;
        // Already past the line (or too close to stop): keep going through the crossing.
        if (d > -0.5) limit = Math.min(limit, Math.max(0, d));
      }
    }
    for (const other of cars) {
      if (other === car || other.lane !== car.lane) continue;
      const d = ahead(other.s);
      if (d > 0) limit = Math.min(limit, d - GAP);
    }
    if (player) {
      const side = lane.axis === "z" ? player.x - lane.at : player.z - lane.at;
      const along = lane.axis === "z" ? player.z : player.x;
      const d = ahead(along);
      if (Math.abs(side) < 2 && d > -1) limit = Math.min(limit, d - CAR_HALF - 1.5);
    }

    // Brake so that it stops within `limit` meters.
    const target = limit <= 0 ? 0 : Math.min(CRUISE, Math.sqrt(2 * BRAKE * limit));
    if (car.speed > target) car.speed = Math.max(target, car.speed - BRAKE * dt * 1.5);
    else car.speed = Math.min(target, car.speed + ACCEL * dt);
    car.s += lane.dir * car.speed * dt;

    // Off the end of the lane: come back in at the start.
    const end = lane.dir > 0 ? lane.to : lane.from;
    if ((car.s - end) * lane.dir > 0) car.s = lane.dir > 0 ? lane.from : lane.to;
  }
}
