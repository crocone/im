import * as THREE from 'three';

export const clamp = (v: number, lo: number, hi: number) => (v < lo ? lo : v > hi ? hi : v);
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const smoothstep = (a: number, b: number, v: number) => {
  const t = clamp((v - a) / (b - a), 0, 1);
  return t * t * (3 - 2 * t);
};
/** Frame-rate independent exponential smoothing factor. */
export const damp = (rate: number, dt: number) => 1 - Math.exp(-rate * dt);
export const rand = (a: number, b: number) => a + Math.random() * (b - a);
export const randSign = () => (Math.random() < 0.5 ? -1 : 1);
export const pick = <T>(arr: readonly T[]): T => arr[Math.floor(Math.random() * arr.length)];

export const UP = new THREE.Vector3(0, 1, 0);
export const FORWARD = new THREE.Vector3(0, 0, 1);
/** Local right axis of every model (models face +Z, so their right hand points to -X). */
export const RIGHT = new THREE.Vector3(-1, 0, 0);

/** Deterministic PRNG (mulberry32) used for the city layout. */
export function seeded(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Rotate unit vector ``from`` toward unit vector ``to`` by at most ``maxAngle`` radians (in place). */
export function rotateToward(from: THREE.Vector3, to: THREE.Vector3, maxAngle: number): THREE.Vector3 {
  const d = clamp(from.dot(to), -1, 1);
  const angle = Math.acos(d);
  if (angle < 1e-5) return from.copy(to);
  const t = Math.min(1, maxAngle / angle);
  if (angle > Math.PI - 1e-3) {
    // opposite vectors: rotate around any perpendicular axis
    const axis = Math.abs(from.y) < 0.9 ? UP : FORWARD;
    _tmpAxis.crossVectors(from, axis).normalize();
    return from.applyAxisAngle(_tmpAxis, Math.min(maxAngle, angle));
  }
  _tmpAxis.crossVectors(from, to).normalize();
  return from.applyAxisAngle(_tmpAxis, angle * t).normalize();
}
const _tmpAxis = new THREE.Vector3();

/**
 * Time for a projectile of speed ``speed`` fired from ``from`` to meet a target at ``pos`` moving
 * with ``vel``. Returns the smallest positive solution or the naive distance/speed estimate.
 */
export function interceptTime(from: THREE.Vector3, pos: THREE.Vector3, vel: THREE.Vector3, speed: number): number {
  const dx = pos.x - from.x;
  const dy = pos.y - from.y;
  const dz = pos.z - from.z;
  const a = vel.lengthSq() - speed * speed;
  const b = 2 * (dx * vel.x + dy * vel.y + dz * vel.z);
  const c = dx * dx + dy * dy + dz * dz;
  const naive = Math.sqrt(c) / speed;
  if (Math.abs(a) < 1e-6) {
    const t = -c / b;
    return t > 0 ? t : naive;
  }
  const disc = b * b - 4 * a * c;
  if (disc < 0) return naive;
  const sq = Math.sqrt(disc);
  const t1 = (-b - sq) / (2 * a);
  const t2 = (-b + sq) / (2 * a);
  const t = t1 > 0 && t2 > 0 ? Math.min(t1, t2) : Math.max(t1, t2);
  return t > 0 ? t : naive;
}

/** Quaternion that makes a +Z-forward model look along ``dir`` with ``up`` as reference. */
export function quatFromForward(dir: THREE.Vector3, up: THREE.Vector3, out: THREE.Quaternion) {
  // Matrix4.lookAt(eye, target, up) points +Z from target to eye: eye = dir, target = 0 gives +Z = dir.
  _m.lookAt(dir, _zero, Math.abs(dir.dot(up)) > 0.999 ? FORWARD : up);
  return out.setFromRotationMatrix(_m);
}
const _m = new THREE.Matrix4();
const _zero = new THREE.Vector3();

/** Cheap smooth 1D noise in [-1, 1] (sum of incommensurate sines). */
export function wobble(t: number, seed = 0) {
  return (
    Math.sin(t * 1.7 + seed * 12.9898) * 0.5 +
    Math.sin(t * 3.1 + seed * 78.233) * 0.3 +
    Math.sin(t * 5.3 + seed * 37.719) * 0.2
  );
}
