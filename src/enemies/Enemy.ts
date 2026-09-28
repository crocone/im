import * as THREE from 'three';
import type { GameContext } from '../game/Context';
import type { HitInfo, Hittable, RAPIER } from '../physics/Physics';

export type EnemyKind = 'drone' | 'turret' | 'boss';

let nextId = 1;

/** Anything a homing missile can chase. */
export interface MissileTarget {
  readonly position: THREE.Vector3;
  readonly velocity: THREE.Vector3;
  readonly radius: number;
  readonly alive: boolean;
}

/** Common enemy state: health, hittable registration, lock-on metadata and cleanup. */
export abstract class Enemy implements Hittable, MissileTarget {
  readonly id = nextId++;
  abstract readonly kind: EnemyKind;
  abstract readonly label: string;
  readonly position = new THREE.Vector3();
  readonly velocity = new THREE.Vector3();
  readonly root = new THREE.Group();
  radius = 2;
  lockTime = 1;
  health: number;
  alive = true;
  /** ready to be removed from the manager */
  removed = false;
  protected body: RAPIER.RigidBody | null = null;
  protected colliders: RAPIER.Collider[] = [];
  protected hitFlash = 0;

  constructor(protected readonly ctx: GameContext, readonly maxHealth: number) {
    this.health = maxHealth;
    ctx.scene.add(this.root);
  }

  /** Whether the targeting computer may lock this enemy right now. */
  get lockable() {
    return this.alive;
  }

  abstract update(dt: number): void;

  hit(info: HitInfo) {
    if (!this.alive) return;
    this.applyDamage(info.damage, info);
  }

  protected applyDamage(amount: number, info: HitInfo) {
    if (!this.alive || amount <= 0) return;
    this.health -= amount;
    this.hitFlash = 1;
    this.onDamaged(info);
    if (this.health <= 0) {
      this.health = 0;
      this.alive = false;
      this.onDestroyed(info);
    }
  }

  protected onDamaged(_info: HitInfo) {}

  protected abstract onDestroyed(info: HitInfo): void;

  protected registerBody(body: RAPIER.RigidBody, colliders: RAPIER.Collider[], owner: Hittable = this) {
    this.body = body;
    this.colliders.push(...colliders);
    for (const c of colliders) this.ctx.physics.register(c, owner);
  }

  /** Remove the physics body and the scene graph (called once by the manager). */
  dispose() {
    if (this.body) {
      this.ctx.physics.removeBody(this.body);
      this.body = null;
    }
    this.colliders = [];
    this.ctx.scene.remove(this.root);
  }
}
