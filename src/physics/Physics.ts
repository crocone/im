import RAPIER from '@dimforge/rapier3d-compat';
import * as THREE from 'three';

/** Collision membership bits. Every collider also accepts the QUERY bit so raycasts can reach it. */
export const G = {
  WORLD: 1 << 0,
  PLAYER: 1 << 1,
  ENEMY: 1 << 2,
  SHIELD: 1 << 3,
  PLAYER_MISSILE: 1 << 4,
  ENEMY_MISSILE: 1 << 5,
  DEBRIS: 1 << 6,
  /** invisible arena walls: they only stop the player */
  BOUNDARY: 1 << 7,
  QUERY: 1 << 15,
} as const;

/** Rapier interaction groups: upper 16 bits = membership, lower 16 bits = what it collides with. */
export function groups(membership: number, filter: number): number {
  return (((membership & 0xffff) << 16) | ((filter | G.QUERY) & 0xffff)) >>> 0;
}

export function queryGroups(mask: number): number {
  return ((G.QUERY << 16) | (mask & 0xffff)) >>> 0;
}

export type HitSource = 'repulsor' | 'missile' | 'mini' | 'explosion' | 'enemy' | 'collision';
export type HittableKind = 'drone' | 'turret' | 'boss' | 'shield' | 'enemyMissile' | 'destructible' | 'player';

export interface HitInfo {
  damage: number;
  point: THREE.Vector3;
  dir: THREE.Vector3;
  source: HitSource;
  impulse: number;
}

/** Anything a weapon can damage. Colliders are mapped to their owner through ``Physics.register``. */
export interface Hittable {
  readonly kind: HittableKind;
  hit(info: HitInfo): void;
}

export interface RayHit {
  point: THREE.Vector3;
  normal: THREE.Vector3;
  distance: number;
  collider: RAPIER.Collider;
  owner: Hittable | undefined;
}

export class Physics {
  readonly world: RAPIER.World;
  private readonly owners = new Map<number, Hittable>();
  private readonly ray = new RAPIER.Ray({ x: 0, y: 0, z: 0 }, { x: 0, y: 0, z: 1 });

  static async create(): Promise<Physics> {
    await RAPIER.init();
    return new Physics();
  }

  private constructor() {
    this.world = new RAPIER.World({ x: 0, y: -9.81, z: 0 });
  }

  register(collider: RAPIER.Collider, owner: Hittable) {
    this.owners.set(collider.handle, owner);
  }

  unregister(collider: RAPIER.Collider) {
    this.owners.delete(collider.handle);
  }

  owner(collider: RAPIER.Collider): Hittable | undefined {
    return this.owners.get(collider.handle);
  }

  /**
   * Advance the simulation by the frame time. Variable step (clamped) keeps motion smooth on
   * high refresh displays; long frames are split into sub-steps of at most 1/30 s.
   */
  step(dt: number, beforeStep?: (h: number) => void) {
    let remaining = Math.min(dt, 0.1);
    while (remaining > 1e-4) {
      const h = Math.min(remaining, 1 / 30);
      this.world.timestep = Math.max(h, 1 / 240);
      beforeStep?.(h);
      this.world.step();
      remaining -= h;
    }
  }

  raycast(
    origin: THREE.Vector3,
    dir: THREE.Vector3,
    maxDist: number,
    mask: number,
    exclude?: RAPIER.Collider,
  ): RayHit | null {
    this.ray.origin = { x: origin.x, y: origin.y, z: origin.z };
    this.ray.dir = { x: dir.x, y: dir.y, z: dir.z };
    const hit = this.world.castRayAndGetNormal(this.ray, maxDist, true, undefined, queryGroups(mask), exclude);
    if (!hit) return null;
    const t = hit.timeOfImpact;
    return {
      point: new THREE.Vector3(origin.x + dir.x * t, origin.y + dir.y * t, origin.z + dir.z * t),
      normal: new THREE.Vector3(hit.normal.x, hit.normal.y, hit.normal.z),
      distance: t,
      collider: hit.collider,
      owner: this.owners.get(hit.collider.handle),
    };
  }

  /** Segment test between two points (used for projectile continuous collision). */
  segment(from: THREE.Vector3, to: THREE.Vector3, mask: number, exclude?: RAPIER.Collider): RayHit | null {
    _dir.subVectors(to, from);
    const len = _dir.length();
    if (len < 1e-6) return null;
    _dir.divideScalar(len);
    return this.raycast(from, _dir, len, mask, exclude);
  }

  lineOfSight(from: THREE.Vector3, to: THREE.Vector3): boolean {
    return this.segment(from, to, G.WORLD) === null;
  }

  fixedCuboid(center: THREE.Vector3, half: THREE.Vector3, quat: THREE.Quaternion, membership = G.WORLD,
    filter = G.PLAYER | G.DEBRIS) {
    const desc = RAPIER.ColliderDesc.cuboid(half.x, half.y, half.z)
      .setTranslation(center.x, center.y, center.z)
      .setRotation({ x: quat.x, y: quat.y, z: quat.z, w: quat.w })
      .setCollisionGroups(groups(membership, filter))
      .setFriction(0.6);
    return this.world.createCollider(desc);
  }

  fixedCylinder(center: THREE.Vector3, radius: number, halfHeight: number, membership = G.WORLD,
    filter = G.PLAYER | G.DEBRIS) {
    const desc = RAPIER.ColliderDesc.cylinder(halfHeight, radius)
      .setTranslation(center.x, center.y, center.z)
      .setCollisionGroups(groups(membership, filter))
      .setFriction(0.6);
    return this.world.createCollider(desc);
  }

  /** Kinematic body with a single collider (enemies, projectiles). */
  kinematic(desc: RAPIER.ColliderDesc, position: THREE.Vector3, membership: number, filter: number) {
    const body = this.world.createRigidBody(
      RAPIER.RigidBodyDesc.kinematicPositionBased().setTranslation(position.x, position.y, position.z),
    );
    const collider = this.world.createCollider(desc.setCollisionGroups(groups(membership, filter)), body);
    return { body, collider };
  }

  removeBody(body: RAPIER.RigidBody) {
    for (let i = 0; i < body.numColliders(); i++) this.unregister(body.collider(i));
    this.world.removeRigidBody(body);
  }

  removeCollider(collider: RAPIER.Collider) {
    this.unregister(collider);
    this.world.removeCollider(collider, true);
  }
}

const _dir = new THREE.Vector3();

export { RAPIER };
