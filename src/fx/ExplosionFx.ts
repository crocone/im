import * as THREE from 'three';
import { rand } from '../game/math';
import type { LightPool } from './LightPool';
import type { Particles } from './Particles';

export interface ExplosionOptions {
  /** overall scale; 1 = missile sized */
  scale?: number;
  smoke?: number;
  sparks?: number;
  shockwave?: boolean;
  tint?: THREE.Color;
  light?: boolean;
}

const _v = new THREE.Vector3();
const _p = new THREE.Vector3();
const FIRE_A = new THREE.Color(2.8, 1.4, 0.45);
const FIRE_B = new THREE.Color(0.5, 0.1, 0.02);
const FLASH = new THREE.Color(4, 3.2, 2.2);
const SMOKE_A = new THREE.Color(0.2, 0.18, 0.17);
const SMOKE_B = new THREE.Color(0.1, 0.095, 0.09);
const SPARK = new THREE.Color(4, 2.4, 1.0);
const RING = new THREE.Color(1.6, 1.1, 0.8);

function randomDir(out: THREE.Vector3) {
  do out.set(rand(-1, 1), rand(-1, 1), rand(-1, 1));
  while (out.lengthSq() > 1 || out.lengthSq() < 0.01);
  return out.normalize();
}

/** Layered explosion: flash, fireballs, sparks, smoke, shock ring and a short-lived light. */
export class ExplosionFx {
  constructor(
    private readonly glow: Particles,
    private readonly smoke: Particles,
    private readonly sparks: Particles,
    private readonly rings: Particles,
    private readonly lights: LightPool,
  ) {}

  spawn(pos: THREE.Vector3, opts: ExplosionOptions = {}) {
    const s = opts.scale ?? 1;
    const fireA = opts.tint ? _tint.copy(FIRE_A).multiply(opts.tint) : FIRE_A;
    this.glow.emit({ pos, life: 0.22, size: 5 * s, size1: 16 * s, color: FLASH, alpha: 1, alpha1: 0 });
    const fireballs = Math.round(10 + 8 * Math.sqrt(s));
    for (let i = 0; i < fireballs; i++) {
      randomDir(_v);
      _p.copy(pos).addScaledVector(_v, rand(0, 1.2) * s);
      this.glow.emit({
        pos: _p,
        vel: _v.clone().multiplyScalar(rand(4, 14) * s),
        life: rand(0.4, 0.85),
        size: rand(2, 3.5) * s,
        size1: rand(5, 8) * s,
        color: fireA,
        color1: FIRE_B,
        alpha: 1,
        alpha1: 0,
        drag: 3,
        gravity: -2,
      });
    }
    const smoke = opts.smoke ?? Math.round(8 + 6 * s);
    for (let i = 0; i < smoke; i++) {
      randomDir(_v);
      _v.y = Math.abs(_v.y) * 0.8 + 0.2;
      _p.copy(pos).addScaledVector(_v, rand(0, 1.5) * s);
      this.smoke.emit({
        pos: _p,
        vel: _v.clone().multiplyScalar(rand(2, 7) * s),
        life: rand(2.2, 3.8),
        size: rand(3, 5) * s,
        size1: rand(10, 16) * s,
        color: SMOKE_A,
        color1: SMOKE_B,
        alpha: 0.8,
        alpha1: 0,
        drag: 1.4,
        gravity: -1.2,
        spin: rand(-0.6, 0.6),
      });
    }
    this.sparkBurst(pos, null, opts.sparks ?? Math.round(18 + 16 * s), 35 * Math.sqrt(s), SPARK);
    if (opts.shockwave) {
      this.rings.emit({ pos, life: 0.45, size: 2 * s, size1: 34 * s, color: RING, alpha: 0.9, alpha1: 0 });
    }
    if (opts.light !== false) this.lights.flash(pos, 0xffa25a, 2600 * s, 90 * Math.sqrt(s), 0.45);
  }

  /** Directional spark shower (impacts) or omni burst (normal = null). */
  sparkBurst(pos: THREE.Vector3, normal: THREE.Vector3 | null, count: number, speed: number, color = SPARK) {
    for (let i = 0; i < count; i++) {
      randomDir(_v);
      if (normal) {
        if (_v.dot(normal) < 0) _v.reflect(normal);
        _v.addScaledVector(normal, 0.8).normalize();
      }
      this.sparks.emit({
        pos,
        vel: _v.multiplyScalar(rand(0.35, 1) * speed).clone(),
        life: rand(0.25, 0.8),
        size: rand(0.12, 0.28),
        size1: 0.05,
        color,
        alpha: 1,
        alpha1: 0.2,
        drag: 1.2,
        gravity: 14,
      });
    }
  }
}

const _tint = new THREE.Color();
