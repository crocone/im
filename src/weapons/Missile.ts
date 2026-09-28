import * as THREE from 'three';
import type { MissileTarget } from '../enemies/Enemy';
import type { GameContext } from '../game/Context';
import { interceptTime, quatFromForward, rotateToward, smoothstep, UP } from '../game/math';
import { G, RAPIER, type HitInfo, type Hittable } from '../physics/Physics';

export type MissileKind = 'homing' | 'mini' | 'enemy';

interface Spec {
  maxSpeed: number;
  accel: number;
  ignition: number;
  guideStart: number;
  guideBlend: number;
  turnRate: number;
  life: number;
  proximity: number;
  damage: number;
  blast: number;
  scale: number;
  trailSpacing: number;
  trailSize: number;
  trailLife: number;
  colliderRadius: number;
  membership: number;
  mask: number;
}

const SPECS: Record<MissileKind, Spec> = {
  homing: {
    maxSpeed: 150, accel: 150, ignition: 0.14, guideStart: 0.22, guideBlend: 0.55, turnRate: 4.4, life: 7,
    proximity: 2.5, damage: 150, blast: 8, scale: 1.25, trailSpacing: 0.6, trailSize: 1.2, trailLife: 2.4,
    colliderRadius: 0.35, membership: G.PLAYER_MISSILE, mask: G.WORLD | G.ENEMY | G.SHIELD | G.DEBRIS,
  },
  mini: {
    maxSpeed: 128, accel: 210, ignition: 0.05, guideStart: 0.12, guideBlend: 0.3, turnRate: 7, life: 4.2,
    proximity: 2.5, damage: 55, blast: 4.5, scale: 0.65, trailSpacing: 0.7, trailSize: 0.8, trailLife: 1.4,
    colliderRadius: 0.2, membership: G.PLAYER_MISSILE, mask: G.WORLD | G.ENEMY | G.SHIELD | G.DEBRIS,
  },
  enemy: {
    maxSpeed: 74, accel: 60, ignition: 0.1, guideStart: 0.3, guideBlend: 0.7, turnRate: 1.3, life: 9,
    proximity: 3, damage: 20, blast: 6, scale: 1.0, trailSpacing: 0.7, trailSize: 1.0, trailLife: 2.2,
    colliderRadius: 1.8, membership: G.ENEMY_MISSILE, mask: G.WORLD | G.PLAYER | G.DEBRIS,
  },
};

const PARK = { x: 0, y: -500, z: 0 };
const _next = new THREE.Vector3();
const _desired = new THREE.Vector3();
const _aim = new THREE.Vector3();
const _tail = new THREE.Vector3();
const _start = new THREE.Vector3();
const EXHAUST_PLAYER = new THREE.Color(3.2, 2.0, 1.0);
const EXHAUST_ENEMY = new THREE.Color(3.4, 0.9, 0.5);

/**
 * A physical guided missile: Rapier kinematic body (so repulsors can shoot it down), boost-out
 * phase along its launch vector, then guidance blended in with a finite turn rate.
 */
export class Missile implements Hittable {
  readonly kind = 'enemyMissile' as const;
  readonly spec: Spec;
  readonly mesh: THREE.Object3D;
  readonly position = new THREE.Vector3();
  readonly velocity = new THREE.Vector3();
  readonly radius = 1;
  active = false;
  alive = false;
  target: MissileTarget | null = null;
  private readonly aimPoint = new THREE.Vector3();
  private hasAim = false;
  private readonly dir = new THREE.Vector3();
  private readonly drift = new THREE.Vector3();
  private speed = 0;
  private age = 0;
  private lastDist = Infinity;
  private trailCarry = 0;
  private readonly body: RAPIER.RigidBody;
  private readonly collider: RAPIER.Collider;
  private readonly exhaust: THREE.Object3D;

  constructor(private readonly ctx: GameContext, readonly type: MissileKind, template: THREE.Object3D) {
    this.spec = SPECS[type];
    this.mesh = template.clone(true);
    this.mesh.scale.setScalar(this.spec.scale);
    this.mesh.visible = false;
    this.exhaust = this.mesh.getObjectByName('Exhaust') ?? this.mesh;
    ctx.scene.add(this.mesh);
    const k = ctx.physics.kinematic(
      RAPIER.ColliderDesc.ball(this.spec.colliderRadius).setSensor(true),
      new THREE.Vector3(PARK.x, PARK.y, PARK.z),
      this.spec.membership,
      0,
    );
    this.body = k.body;
    this.collider = k.collider;
    this.collider.setEnabled(false);
    if (type === 'enemy') ctx.physics.register(this.collider, this);
  }

  launch(pos: THREE.Vector3, dir: THREE.Vector3, speed: number, inherit: THREE.Vector3, target: MissileTarget | null,
    aim?: THREE.Vector3) {
    this.active = this.alive = true;
    this.position.copy(pos);
    this.dir.copy(dir).normalize();
    this.speed = speed;
    this.drift.copy(inherit);
    this.target = target;
    this.hasAim = !!aim;
    if (aim) this.aimPoint.copy(aim);
    this.age = 0;
    this.lastDist = Infinity;
    this.trailCarry = 0;
    this.mesh.visible = true;
    this.body.setTranslation(pos, true);
    this.collider.setEnabled(true);
    this.orient();
    this.ctx.fx.smoke.emit({ pos, vel: dir.clone().multiplyScalar(-4), life: 1.2, size: 1.2 * this.spec.scale, size1: 4,
      color: new THREE.Color(0.7, 0.68, 0.66), alpha: 0.6, alpha1: 0, drag: 2 });
  }

  private orient() {
    quatFromForward(this.dir, UP, this.mesh.quaternion);
    this.mesh.position.copy(this.position);
  }

  update(dt: number) {
    if (!this.active) return;
    const s = this.spec;
    this.age += dt;
    if (this.age > s.ignition) this.speed = Math.min(s.maxSpeed, this.speed + s.accel * dt);
    // guidance: blend in after the boost-out so the missile arcs away from the launcher first
    const guide = smoothstep(s.guideStart, s.guideStart + s.guideBlend, this.age);
    const tgt = this.target && this.target.alive ? this.target : null;
    const dist = tgt ? this.position.distanceTo(tgt.position) : Infinity;
    if (guide > 0 && (tgt || this.hasAim)) {
      let turn = s.turnRate;
      if (tgt) {
        // lead the target to the intercept point; tighten the turn in the terminal phase
        const tti = interceptTime(this.position, tgt.position, tgt.velocity, Math.max(this.speed, 30));
        _aim.copy(tgt.position).addScaledVector(tgt.velocity, Math.min(tti, 3));
        if (dist < 60) turn *= 1 + (60 - dist) / 30;
      } else _aim.copy(this.aimPoint);
      _desired.subVectors(_aim, this.position).normalize();
      rotateToward(this.dir, _desired, turn * guide * dt);
    }
    this.drift.multiplyScalar(Math.exp(-2.5 * dt));
    this.velocity.copy(this.dir).multiplyScalar(this.speed).add(this.drift);
    _next.copy(this.position).addScaledVector(this.velocity, dt);
    // contact: swept ray from the previous position
    const hit = this.ctx.physics.segment(this.position, _next, s.mask, this.collider);
    if (hit) {
      this.position.copy(hit.point).addScaledVector(hit.normal, 0.3);
      this.explode(hit.owner ?? null);
      return;
    }
    // proximity fuse, plus a closest-approach fuse so near misses detonate instead of orbiting
    if (tgt && _next.distanceTo(tgt.position) < tgt.radius + s.proximity) {
      this.position.copy(_next);
      this.explode(this.type === 'enemy' ? null : (tgt as unknown as Hittable));
      return;
    }
    if (tgt && guide > 0.5 && dist < tgt.radius + s.blast * 1.4 && dist > this.lastDist + 0.05) {
      this.explode(null);
      return;
    }
    this.lastDist = dist;
    // trail + exhaust
    _tail.copy(this.dir).multiplyScalar(-0.8 * s.scale).add(_next);
    this.trailCarry = this.ctx.fx.trail(_start.copy(this.position).addScaledVector(this.dir, -0.8 * s.scale), _tail,
      s.trailSpacing, s.trailSize, s.trailLife, this.trailCarry);
    this.ctx.fx.exhaust(_tail, 1.3 * s.scale, this.type === 'enemy' ? EXHAUST_ENEMY : EXHAUST_PLAYER);
    this.position.copy(_next);
    this.body.setNextKinematicTranslation(this.position);
    this.orient();
    const flicker = 0.8 + Math.random() * 0.5;
    this.exhaust.scale.setScalar(flicker);
    if (this.age > s.life) this.explode(null);
  }

  /** Repulsor interception (enemy missiles only). */
  hit(info: HitInfo) {
    if (!this.active || this.type !== 'enemy') return;
    this.ctx.score.intercept(this.position);
    this.explode(null, info.source === 'repulsor');
  }

  explode(direct: Hittable | null, intercepted = false) {
    if (!this.active) return;
    const s = this.spec;
    this.ctx.combat.explosion(this.position, {
      radius: s.blast,
      damage: intercepted ? 0 : s.damage,
      scale: s.scale * (intercepted ? 0.8 : 1),
      source: this.type === 'enemy' ? 'enemy' : this.type === 'mini' ? 'mini' : 'missile',
      direct,
    });
    this.deactivate();
  }

  deactivate() {
    this.active = this.alive = false;
    this.target = null;
    this.mesh.visible = false;
    this.collider.setEnabled(false);
    this.body.setTranslation(PARK, false);
  }
}

/** Fixed-size pool of missiles of one type. */
export class MissilePool {
  readonly items: Missile[] = [];

  constructor(ctx: GameContext, type: MissileKind, template: THREE.Object3D, size: number) {
    for (let i = 0; i < size; i++) this.items.push(new Missile(ctx, type, template));
  }

  acquire(): Missile | null {
    return this.items.find((m) => !m.active) ?? null;
  }

  update(dt: number) {
    for (const m of this.items) if (m.active) m.update(dt);
  }

  clear() {
    for (const m of this.items) if (m.active) m.deactivate();
  }
}
