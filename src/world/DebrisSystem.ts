import * as THREE from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import type { GameContext } from '../game/Context';
import { TUNING } from '../game/constants';
import { rand } from '../game/math';
import { G, groups, RAPIER } from '../physics/Physics';

/** One fracture chunk authored in Blender (chunk_###), ready to be instantiated as debris. */
export interface ChunkTemplate {
  parts: { geometry: THREE.BufferGeometry; material: THREE.Material }[];
  local: THREE.Matrix4;
  hull: Float32Array;
}

interface Chunk {
  mesh: THREE.Group;
  body: RAPIER.RigidBody | null;
  age: number;
  pile: Pile;
}

interface Pile {
  chunks: Chunk[];
  frozen: number;
  merged: THREE.Group | null;
}

/** Global cap on simultaneously simulated debris bodies (oldest chunks are frozen first). */
export const MAX_ACTIVE_DEBRIS = TUNING.debris.maxActive;
/** Seconds a chunk is simulated before it is frozen in place and its Rapier body removed. */
export const DEBRIS_LIFETIME = TUNING.debris.lifetime;

const _m = new THREE.Matrix4();
const _p = new THREE.Vector3();
const _q = new THREE.Quaternion();
const _s = new THREE.Vector3();
const _dir = new THREE.Vector3();

/**
 * Physical debris with a strict budget: at most MAX_ACTIVE dynamic Rapier bodies; chunks freeze
 * after their lifetime (or when the budget overflows, oldest first). Once a whole pile is frozen
 * its chunks are merged into one static mesh per material, and old piles are recycled.
 */
export class DebrisSystem {
  private readonly active: Chunk[] = [];
  private readonly piles: Pile[] = [];
  private readonly byCollider = new Map<number, Chunk>();

  constructor(private readonly ctx: GameContext) {}

  get activeCount() {
    return this.active.length;
  }

  spawn(templates: ChunkTemplate[], world: THREE.Matrix4, center: THREE.Vector3, strength: number) {
    const pile: Pile = { chunks: [], frozen: 0, merged: null };
    const { physics, scene } = this.ctx;
    for (const t of templates) {
      const mesh = new THREE.Group();
      for (const part of t.parts) {
        const m = new THREE.Mesh(part.geometry, part.material);
        m.castShadow = true;
        m.receiveShadow = true;
        mesh.add(m);
      }
      _m.multiplyMatrices(world, t.local).decompose(_p, _q, _s);
      mesh.position.copy(_p);
      mesh.quaternion.copy(_q);
      scene.add(mesh);
      const body = physics.world.createRigidBody(
        RAPIER.RigidBodyDesc.dynamic().setTranslation(_p.x, _p.y, _p.z).setRotation(_q).setLinearDamping(0.15).setAngularDamping(0.4).setCcdEnabled(false),
      );
      const desc = (RAPIER.ColliderDesc.convexHull(t.hull) ?? RAPIER.ColliderDesc.ball(0.4))
        .setDensity(1)
        .setFriction(0.8)
        .setRestitution(0.15)
        .setCollisionGroups(groups(G.DEBRIS, G.WORLD | G.DEBRIS | G.PLAYER | G.ENEMY));
      const collider = physics.world.createCollider(desc, body);
      // push outward from the blast centre, plus tumble
      _dir.subVectors(_p, center);
      const d = _dir.length();
      _dir.normalize().add(new THREE.Vector3(rand(-0.35, 0.35), rand(0.2, 0.8), rand(-0.35, 0.35))).normalize();
      const speed = (strength * rand(0.6, 1.3)) / (1 + d * 0.12);
      body.setLinvel({ x: _dir.x * speed, y: _dir.y * speed, z: _dir.z * speed }, true);
      body.setAngvel({ x: rand(-6, 6), y: rand(-6, 6), z: rand(-6, 6) }, true);
      const chunk: Chunk = { mesh, body, age: 0, pile };
      this.byCollider.set(collider.handle, chunk);
      pile.chunks.push(chunk);
      this.active.push(chunk);
    }
    this.piles.push(pile);
    while (this.active.length > MAX_ACTIVE_DEBRIS) this.freeze(this.active[0]);
    while (this.piles.length > TUNING.debris.maxFrozenPiles) this.removePile(this.piles[0]);
  }

  /** Nudge a debris chunk hit by a weapon (no-op for non-debris colliders). */
  impulseAt(collider: RAPIER.Collider, point: THREE.Vector3, dir: THREE.Vector3, strength: number) {
    const chunk = this.byCollider.get(collider.handle);
    if (!chunk?.body) return;
    const m = chunk.body.mass();
    chunk.body.applyImpulseAtPoint({ x: dir.x * strength * m, y: dir.y * strength * m, z: dir.z * strength * m }, point, true);
  }

  explosionImpulse(center: THREE.Vector3, radius: number, strength: number) {
    for (const c of this.active) {
      if (!c.body) continue;
      const t = c.body.translation();
      _dir.set(t.x - center.x, t.y - center.y, t.z - center.z);
      const d = _dir.length();
      if (d > radius) continue;
      _dir.normalize().y += 0.3;
      const k = strength * (1 - d / radius) * c.body.mass();
      c.body.applyImpulse({ x: _dir.x * k, y: _dir.y * k, z: _dir.z * k }, true);
    }
  }

  update(dt: number) {
    for (let i = this.active.length - 1; i >= 0; i--) {
      const c = this.active[i];
      c.age += dt;
      const t = c.body!.translation();
      const r = c.body!.rotation();
      c.mesh.position.set(t.x, t.y, t.z);
      c.mesh.quaternion.set(r.x, r.y, r.z, r.w);
      if (c.age > DEBRIS_LIFETIME || t.y < -20 || (c.age > 1.5 && c.body!.isSleeping())) this.freeze(c);
    }
  }

  /** Stop simulating a chunk: remove its Rapier body and keep the mesh where it came to rest. */
  private freeze(c: Chunk) {
    if (!c.body) return;
    for (let i = 0; i < c.body.numColliders(); i++) this.byCollider.delete(c.body.collider(i).handle);
    this.ctx.physics.world.removeRigidBody(c.body);
    c.body = null;
    const idx = this.active.indexOf(c);
    if (idx >= 0) this.active.splice(idx, 1);
    c.pile.frozen++;
    if (c.pile.frozen === c.pile.chunks.length) this.mergePile(c.pile);
  }

  private mergePile(pile: Pile) {
    const byMaterial = new Map<THREE.Material, THREE.BufferGeometry[]>();
    for (const c of pile.chunks) {
      c.mesh.updateMatrixWorld(true);
      for (const child of c.mesh.children) {
        const m = child as THREE.Mesh;
        const g = normalized(m.geometry).applyMatrix4(m.matrixWorld);
        const mat = m.material as THREE.Material;
        if (!byMaterial.has(mat)) byMaterial.set(mat, []);
        byMaterial.get(mat)!.push(g);
      }
    }
    const group = new THREE.Group();
    for (const [mat, geos] of byMaterial) {
      const merged = mergeGeometries(geos, false);
      for (const g of geos) g.dispose();
      if (!merged) continue;
      const mesh = new THREE.Mesh(merged, mat);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      group.add(mesh);
    }
    for (const c of pile.chunks) this.ctx.scene.remove(c.mesh);
    this.ctx.scene.add(group);
    pile.merged = group;
  }

  private removePile(pile: Pile) {
    for (const c of pile.chunks) {
      if (c.body) this.freeze(c);
      this.ctx.scene.remove(c.mesh);
    }
    if (pile.merged) {
      this.ctx.scene.remove(pile.merged);
      pile.merged.traverse((o) => (o as THREE.Mesh).geometry?.dispose());
    }
    this.piles.splice(this.piles.indexOf(pile), 1);
  }

  clear() {
    while (this.piles.length) this.removePile(this.piles[0]);
    this.active.length = 0;
    this.byCollider.clear();
  }
}

/** Clone with a uniform attribute set (position, normal, uv) so chunks can be merged. */
function normalized(src: THREE.BufferGeometry) {
  const g = new THREE.BufferGeometry();
  g.setIndex(src.index ? src.index.clone() : null);
  g.setAttribute('position', src.getAttribute('position').clone());
  const count = src.getAttribute('position').count;
  const normal = src.getAttribute('normal');
  g.setAttribute('normal', normal ? normal.clone() : new THREE.BufferAttribute(new Float32Array(count * 3), 3));
  const uv = src.getAttribute('uv');
  g.setAttribute('uv', uv ? uv.clone() : new THREE.BufferAttribute(new Float32Array(count * 2), 2));
  if (!src.index) g.setIndex([...Array(count).keys()]);
  return g;
}
