import * as THREE from 'three';
import { rand } from '../game/math';
import { BeamFx } from './BeamFx';
import { ExplosionFx } from './ExplosionFx';
import { LightPool } from './LightPool';
import { Particles } from './Particles';
import { FxTextures } from './textures';

const SMOKE_TRAIL = new THREE.Color(0.62, 0.6, 0.58);
const SMOKE_TRAIL_END = new THREE.Color(0.35, 0.34, 0.33);
const EXHAUST = new THREE.Color(3.2, 1.9, 0.9);
const MUZZLE = new THREE.Color(1.2, 3.0, 4.0);
const _v = new THREE.Vector3();

/** Owns every pooled effect system; gameplay code talks to effects only through this class. */
export class FxSystem {
  readonly textures = new FxTextures();
  readonly glow: Particles;
  readonly smoke: Particles;
  readonly trails: Particles;
  readonly sparks: Particles;
  readonly rings: Particles;
  readonly lights: LightPool;
  readonly beams: BeamFx;
  readonly explosions: ExplosionFx;

  constructor(scene: THREE.Scene) {
    this.glow = new Particles(3000, this.textures.soft, true);
    this.smoke = new Particles(5000, this.textures.smoke, false);
    this.trails = new Particles(12000, this.textures.puff, false);
    this.sparks = new Particles(2500, this.textures.hard, true, 0.045);
    this.rings = new Particles(64, this.textures.ring, true);
    for (const p of [this.trails, this.smoke, this.glow, this.sparks, this.rings]) scene.add(p.mesh);
    this.lights = new LightPool(scene, 6);
    this.beams = new BeamFx(scene, 16);
    this.explosions = new ExplosionFx(this.glow, this.smoke, this.sparks, this.rings, this.lights);
  }

  /** Smoke puffs laid along a moving emitter's path segment (missile trails). */
  trail(from: THREE.Vector3, to: THREE.Vector3, spacing: number, size: number, life: number, carry = 0) {
    const len = from.distanceTo(to);
    let d = carry;
    while (d < len) {
      _v.lerpVectors(from, to, d / len);
      this.trails.emit({
        pos: _v,
        vel: new THREE.Vector3(rand(-0.6, 0.6), rand(0.2, 1.0), rand(-0.6, 0.6)),
        life: life * rand(0.8, 1.2),
        size: size,
        size1: size * rand(4, 6),
        color: SMOKE_TRAIL,
        color1: SMOKE_TRAIL_END,
        alpha: 0.75,
        alpha1: 0,
        drag: 0.8,
        spin: rand(-0.4, 0.4),
      });
      d += spacing;
    }
    return d - len;
  }

  exhaust(pos: THREE.Vector3, size: number, color = EXHAUST) {
    this.glow.emit({ pos, life: 0.06, size: size, size1: size * 0.5, color, alpha: 1, alpha1: 0 });
  }

  muzzle(pos: THREE.Vector3, size = 0.9, color = MUZZLE) {
    this.glow.emit({ pos, life: 0.09, size, size1: size * 2.2, color, alpha: 1, alpha1: 0 });
  }

  impact(pos: THREE.Vector3, normal: THREE.Vector3, color: THREE.Color, sparks = 10, flash = 1.4) {
    this.glow.emit({ pos, life: 0.12, size: flash, size1: flash * 2, color, alpha: 1, alpha1: 0 });
    this.explosions.sparkBurst(pos, normal, sparks, 22, color);
  }

  update(dt: number, time: number) {
    this.glow.update(dt);
    this.smoke.update(dt);
    this.trails.update(dt);
    this.sparks.update(dt);
    this.rings.update(dt);
    this.lights.update(dt);
    this.beams.update(dt, time);
  }

  clear() {
    this.glow.clear();
    this.smoke.clear();
    this.trails.clear();
    this.sparks.clear();
    this.rings.clear();
    this.lights.clear();
    this.beams.clear();
  }
}
