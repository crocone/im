import * as THREE from 'three';
import type { AssetKey } from '../game/Assets';
import type { GameContext } from '../game/Context';
import { SCORE } from '../game/constants';
import type { HitInfo, HitSource, Hittable, RAPIER } from '../physics/Physics';
import type { DestructibleKind, DestructibleSpot } from './CityProps';
import type { ChunkTemplate } from './DebrisSystem';
import { InstancedKit } from './InstancedKit';

interface KindDef {
  intact: AssetKey;
  fractured: AssetKey;
  health: number;
  label: string;
}

const KINDS: Record<DestructibleKind, KindDef> = {
  column: { intact: 'column', fractured: 'columnFractured', health: 110, label: 'COLUMN' },
  sign: { intact: 'sign', fractured: 'signFractured', health: 60, label: 'BILLBOARD' },
  waterTower: { intact: 'waterTower', fractured: 'waterTowerFractured', health: 140, label: 'WATER TOWER' },
  smallHouse: { intact: 'smallHouse', fractured: 'smallHouseFractured', health: 260, label: 'STRUCTURE' },
};

const SOURCE_MULT: Record<HitSource, number> = { repulsor: 1, missile: 1.2, mini: 1.2, explosion: 1, enemy: 1, collision: 0 };
const DUST = new THREE.Color(0.42, 0.38, 0.33);
const DUST_END = new THREE.Color(0.3, 0.28, 0.25);

class Prop implements Hittable {
  readonly kind = 'destructible' as const;
  hp: number;
  intact = true;
  collider: RAPIER.Collider | null = null;
  readonly center = new THREE.Vector3();

  constructor(
    private readonly system: DestructionSystem,
    readonly type: DestructibleKind,
    readonly index: number,
    readonly matrix: THREE.Matrix4,
    readonly half: THREE.Vector3,
    readonly quat: THREE.Quaternion,
    center: THREE.Vector3,
  ) {
    this.hp = KINDS[type].health;
    this.center.copy(center);
  }

  hit(info: HitInfo) {
    this.system.damage(this, info.damage * SOURCE_MULT[info.source], info.point, info.source === 'repulsor' ? 14 : 24);
  }
}

/**
 * Destructible city props. Intact props are instanced with one fixed Rapier cuboid each; when
 * destroyed the instance is hidden, the collider removed and the Blender-fractured chunks are
 * spawned as dynamic Rapier bodies pushed away from the impact.
 */
export class DestructionSystem {
  private readonly kits = new Map<DestructibleKind, InstancedKit>();
  private readonly chunks = new Map<DestructibleKind, ChunkTemplate[]>();
  private readonly props: Prop[] = [];

  constructor(private readonly ctx: GameContext, spots: DestructibleSpot[]) {
    const counts = new Map<DestructibleKind, number>();
    for (const s of spots) counts.set(s.kind, (counts.get(s.kind) ?? 0) + 1);
    const bounds = new Map<DestructibleKind, THREE.Box3>();
    for (const kind of Object.keys(KINDS) as DestructibleKind[]) {
      const def = KINDS[kind];
      const scene = ctx.assets.scene(def.intact);
      const kit = new InstancedKit(scene, Math.max(1, counts.get(kind) ?? 0), true, true);
      this.kits.set(kind, kit);
      scene.updateMatrixWorld(true);
      bounds.set(kind, new THREE.Box3().setFromObject(scene));
      this.chunks.set(kind, this.loadChunks(def.fractured));
    }
    const up = new THREE.Vector3(0, 1, 0);
    for (const s of spots) {
      const q = new THREE.Quaternion().setFromAxisAngle(up, s.yaw);
      const m = new THREE.Matrix4().compose(s.pos, q, new THREE.Vector3(1, 1, 1));
      const box = bounds.get(s.kind)!;
      const localCenter = box.getCenter(new THREE.Vector3());
      const half = box.getSize(new THREE.Vector3()).multiplyScalar(0.5);
      const center = localCenter.applyMatrix4(m);
      const index = this.kits.get(s.kind)!.add(m);
      const prop = new Prop(this, s.kind, index, m, half, q, center);
      this.props.push(prop);
      this.addCollider(prop);
    }
    for (const kit of this.kits.values()) {
      kit.finish();
      kit.addTo(ctx.scene);
    }
  }

  private loadChunks(key: AssetKey): ChunkTemplate[] {
    const root = this.ctx.assets.scene(key);
    root.updateMatrixWorld(true);
    const inv = root.matrixWorld.clone().invert();
    const out: ChunkTemplate[] = [];
    root.traverse((node) => {
      // chunk nodes are named chunk_###; their primitives get suffixed names (chunk_###_1)
      if (!/^chunk_\d+$/.test(node.name)) return;
      const local = new THREE.Matrix4().multiplyMatrices(inv, node.matrixWorld);
      const nodeInv = node.matrixWorld.clone().invert();
      const parts: ChunkTemplate['parts'] = [];
      const pts: number[] = [];
      const v = new THREE.Vector3();
      node.traverse((o) => {
        const mesh = o as THREE.Mesh;
        if (!mesh.isMesh) return;
        const rel = new THREE.Matrix4().multiplyMatrices(nodeInv, mesh.matrixWorld);
        const geometry = mesh.geometry.clone().applyMatrix4(rel);
        parts.push({ geometry, material: mesh.material as THREE.Material });
        const pos = geometry.getAttribute('position');
        for (let i = 0; i < pos.count; i++) {
          v.fromBufferAttribute(pos, i);
          pts.push(v.x, v.y, v.z);
        }
      });
      if (parts.length) out.push({ parts, local, hull: new Float32Array(pts) });
    });
    return out;
  }

  private addCollider(p: Prop) {
    p.collider = this.ctx.physics.fixedCuboid(p.center, p.half, p.quat);
    this.ctx.physics.register(p.collider, p);
  }

  damage(p: Prop, amount: number, point: THREE.Vector3, strength: number) {
    if (!p.intact || amount <= 0) return;
    p.hp -= amount;
    if (p.hp <= 0) this.shatter(p, point, strength);
  }

  /** Radial damage from explosions. */
  explosion(center: THREE.Vector3, radius: number, damage: number) {
    for (const p of this.props) {
      if (!p.intact) continue;
      const d = p.center.distanceTo(center) - Math.max(p.half.x, p.half.z);
      if (d > radius) continue;
      const falloff = 1 - Math.max(0, d) / radius;
      this.damage(p, damage * (0.35 + 0.65 * falloff), center, 16 + 20 * falloff);
    }
  }

  private shatter(p: Prop, point: THREE.Vector3, strength: number) {
    p.intact = false;
    this.kits.get(p.type)!.hide(p.index);
    if (p.collider) {
      this.ctx.physics.removeCollider(p.collider);
      p.collider = null;
    }
    this.ctx.debris.spawn(this.chunks.get(p.type)!, p.matrix, point, strength);
    // dust burst
    for (let i = 0; i < 10; i++) {
      this.ctx.fx.smoke.emit({
        pos: p.center.clone().add(new THREE.Vector3((Math.random() - 0.5) * p.half.x * 2, (Math.random() - 0.3) * p.half.y * 1.6, (Math.random() - 0.5) * p.half.z * 2)),
        vel: new THREE.Vector3((Math.random() - 0.5) * 6, Math.random() * 3, (Math.random() - 0.5) * 6),
        life: 3 + Math.random() * 2, size: 3, size1: 10, color: DUST, color1: DUST_END, alpha: 0.6, alpha1: 0, drag: 1.2, gravity: -0.3,
      });
    }
    this.ctx.audio.crumble(p.center);
    this.ctx.score.destruct(SCORE.destructible, p.center, KINDS[p.type].label);
  }

  reset() {
    for (const p of this.props) {
      if (p.intact) {
        p.hp = KINDS[p.type].health;
        continue;
      }
      p.intact = true;
      p.hp = KINDS[p.type].health;
      this.kits.get(p.type)!.setMatrix(p.index, p.matrix);
      this.addCollider(p);
    }
  }
}
