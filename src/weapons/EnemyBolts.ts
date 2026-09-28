import * as THREE from 'three';
import type { GameContext } from '../game/Context';
import { quatFromForward, UP } from '../game/math';
import { G } from '../physics/Physics';

interface Bolt {
  pos: THREE.Vector3;
  vel: THREE.Vector3;
  life: number;
  damage: number;
  size: number;
  active: boolean;
}

const MASK = G.WORLD | G.PLAYER | G.DEBRIS;
const GLOW = new THREE.Color(3.5, 0.8, 0.35);
const _next = new THREE.Vector3();
const _dir = new THREE.Vector3();
const _m = new THREE.Matrix4();
const _q = new THREE.Quaternion();
const _s = new THREE.Vector3();
const HIDDEN = new THREE.Matrix4().makeScale(0, 0, 0);

/** Hostile energy bolts (drones, boss): instanced glowing slugs with swept raycast hits. */
export class EnemyBolts {
  private readonly bolts: Bolt[] = [];
  private readonly mesh: THREE.InstancedMesh;

  constructor(private readonly ctx: GameContext, capacity = 256) {
    const geo = new THREE.CapsuleGeometry(0.16, 2.2, 4, 8).rotateX(Math.PI / 2);
    const mat = new THREE.MeshBasicMaterial({
      color: new THREE.Color(4, 1.1, 0.45),
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    this.mesh = new THREE.InstancedMesh(geo, mat, capacity);
    this.mesh.frustumCulled = false;
    this.mesh.count = capacity;
    for (let i = 0; i < capacity; i++) {
      this.mesh.setMatrixAt(i, HIDDEN);
      this.bolts.push({ pos: new THREE.Vector3(), vel: new THREE.Vector3(), life: 0, damage: 0, size: 1, active: false });
    }
    ctx.scene.add(this.mesh);
  }

  fire(pos: THREE.Vector3, vel: THREE.Vector3, damage: number, size = 1) {
    const b = this.bolts.find((x) => !x.active);
    if (!b) return;
    b.pos.copy(pos);
    b.vel.copy(vel);
    b.life = 3;
    b.damage = damage;
    b.size = size;
    b.active = true;
  }

  update(dt: number) {
    const { physics, player, fx } = this.ctx;
    for (let i = 0; i < this.bolts.length; i++) {
      const b = this.bolts[i];
      if (!b.active) continue;
      b.life -= dt;
      _next.copy(b.pos).addScaledVector(b.vel, dt);
      const hit = physics.segment(b.pos, _next, MASK);
      if (hit || b.life <= 0) {
        if (hit) {
          fx.impact(hit.point, hit.normal, GLOW, 8, 1.2 * b.size);
          if (hit.owner === player) {
            _dir.copy(b.vel).normalize();
            player.hit({ damage: b.damage, point: hit.point, dir: _dir.clone(), source: 'enemy', impulse: 0 });
          } else if (!hit.owner) {
            this.ctx.debris.impulseAt(hit.collider, hit.point, _dir.copy(b.vel).normalize(), 2);
          }
        }
        b.active = false;
        this.mesh.setMatrixAt(i, HIDDEN);
        continue;
      }
      b.pos.copy(_next);
      _dir.copy(b.vel).normalize();
      quatFromForward(_dir, UP, _q);
      _s.setScalar(b.size);
      _m.compose(b.pos, _q, _s);
      this.mesh.setMatrixAt(i, _m);
      if (Math.random() < 0.5) fx.glow.emit({ pos: b.pos, life: 0.07, size: 1.4 * b.size, size1: 0.6, color: GLOW, alpha: 0.8, alpha1: 0 });
    }
    this.mesh.instanceMatrix.needsUpdate = true;
  }

  clear() {
    for (let i = 0; i < this.bolts.length; i++) {
      this.bolts[i].active = false;
      this.mesh.setMatrixAt(i, HIDDEN);
    }
    this.mesh.instanceMatrix.needsUpdate = true;
  }
}
