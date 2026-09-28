import * as THREE from 'three';
import type { AssetKey, Assets } from '../game/Assets';
import { TUNING } from '../game/constants';
import { seeded } from '../game/math';
import { G, type Physics } from '../physics/Physics';
import { planCity, type Block } from './CityLayout';
import { CityProps } from './CityProps';
import { InstancedKit } from './InstancedKit';

export type AnchorKind = 'Roof' | 'Small' | 'Top' | 'Pad';

export interface Anchor {
  kind: AnchorKind;
  pos: THREE.Vector3;
  building: number;
  buildingType: number;
  used: boolean;
}

interface ColliderSpec {
  type: 'BOX' | 'CYL';
  matrix: THREE.Matrix4;
}

interface BuildingTemplate {
  kit: InstancedKit;
  colliders: ColliderSpec[];
  anchors: { kind: AnchorKind; pos: THREE.Vector3 }[];
}

export interface BuildingInstance {
  type: number;
  box: THREE.Box3;
}

/** Instanced city: streets, nine building modules, colliders, rooftop anchors and street props. */
export class CityBuilder {
  readonly blocks: Block[];
  readonly anchors: Anchor[] = [];
  readonly buildings: BuildingInstance[] = [];
  readonly spawn = new THREE.Vector3();
  readonly props: CityProps;
  private readonly templates = new Map<number, BuildingTemplate>();

  constructor(private readonly scene: THREE.Scene, private readonly physics: Physics, private readonly assets: Assets) {
    this.blocks = planCity();
    this.buildStreets();
    this.buildBuildings();
    this.props = new CityProps(scene, assets, this, physics);
    this.props.build(seeded(99));
    this.buildBoundary();
  }

  private template(type: number, capacity: number): BuildingTemplate {
    let t = this.templates.get(type);
    if (t) return t;
    const key = `building_0${type}` as AssetKey;
    const root = this.assets.scene(key);
    root.updateMatrixWorld(true);
    const inv = root.matrixWorld.clone().invert();
    t = { kit: new InstancedKit(root, capacity), colliders: [], anchors: [] };
    root.traverse((child) => {
      const local = new THREE.Matrix4().multiplyMatrices(inv, child.matrixWorld);
      if (child.name.startsWith('COL_')) {
        t!.colliders.push({ type: child.name.startsWith('COL_CYL') ? 'CYL' : 'BOX', matrix: local });
      } else if (child.name.startsWith('Anchor_')) {
        const kind = child.name.split('_')[1] as AnchorKind;
        t!.anchors.push({ kind, pos: new THREE.Vector3().setFromMatrixPosition(local) });
      }
    });
    this.templates.set(type, t);
    return t;
  }

  private buildBuildings() {
    const counts = new Map<number, number>();
    for (const b of this.blocks)
      for (const l of b.lots) if (l.lot.use === 'building') counts.set(l.lot.type, (counts.get(l.lot.type) ?? 0) + 1);
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const s = new THREE.Vector3();
    const p = new THREE.Vector3();
    const up = new THREE.Vector3(0, 1, 0);
    const world = new THREE.Matrix4();
    const cp = new THREE.Vector3();
    const cq = new THREE.Quaternion();
    const cs = new THREE.Vector3();
    for (const block of this.blocks) {
      for (const lot of block.lots) {
        if (lot.lot.use !== 'building') continue;
        const { type, rot, scaleY } = lot.lot;
        const t = this.template(type, counts.get(type)!);
        p.set(lot.x, 0.2, lot.z);
        q.setFromAxisAngle(up, rot * (Math.PI / 2));
        s.set(1, scaleY, 1);
        m.compose(p, q, s);
        t.kit.add(m);
        const index = this.buildings.length;
        const box = new THREE.Box3();
        for (const c of t.colliders) {
          world.multiplyMatrices(m, c.matrix);
          world.decompose(cp, cq, cs);
          if (c.type === 'BOX') {
            this.physics.fixedCuboid(cp, cs, cq);
            box.union(new THREE.Box3().setFromCenterAndSize(cp, _v.set(cs.x, cs.y, cs.z).multiplyScalar(2)));
          } else {
            this.physics.fixedCylinder(cp, cs.x, cs.y);
            box.union(new THREE.Box3().setFromCenterAndSize(cp, _v.set(cs.x * 2, cs.y * 2, cs.x * 2)));
          }
        }
        box.expandByScalar(0.5);
        this.buildings.push({ type, box });
        for (const a of t.anchors) {
          const pos = a.pos.clone().applyMatrix4(m);
          this.anchors.push({ kind: a.kind, pos, building: index, buildingType: type, used: false });
          if (a.kind === 'Pad' && block.kind === 'landmark') this.spawn.copy(pos);
        }
      }
    }
    for (const t of this.templates.values()) {
      t.kit.finish();
      t.kit.addTo(this.scene);
    }
  }

  private buildStreets() {
    const n = TUNING.city.blocks;
    const pitch = TUNING.city.pitch;
    const half = (n * pitch) / 2;
    const road = new InstancedKit(this.assets.scene('road'), (n + 1) * n * 2, false, true);
    const junction = new InstancedKit(this.assets.scene('intersection'), (n + 1) * (n + 1), false, true);
    const walk = new InstancedKit(this.assets.scene('sidewalk'), n * n * 4, false, true);
    const plaza = new InstancedKit(this.assets.scene('plaza'), n * n, false, true);
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const up = new THREE.Vector3(0, 1, 0);
    const one = new THREE.Vector3(1, 1, 1);
    const place = (kit: InstancedKit, x: number, z: number, yaw: number) => {
      q.setFromAxisAngle(up, yaw);
      kit.add(m.compose(_v.set(x, 0, z), q, one));
    };
    for (let k = 0; k <= n; k++) {
      const line = -half + k * pitch;
      for (let s = 0; s < n; s++) {
        const mid = -half + pitch / 2 + s * pitch;
        place(road, mid, line, Math.PI / 2);
        place(road, line, mid, 0);
      }
      for (let k2 = 0; k2 <= n; k2++) place(junction, line, -half + k2 * pitch, 0);
    }
    const off = 41.5;
    for (const b of this.blocks) {
      place(plaza, b.x, b.z, 0);
      place(walk, b.x - off, b.z, 0);
      place(walk, b.x + off, b.z, Math.PI);
      place(walk, b.x, b.z - off, -Math.PI / 2);
      place(walk, b.x, b.z + off, Math.PI / 2);
    }
    for (const kit of [road, junction, walk, plaza]) {
      kit.finish();
      kit.addTo(this.scene);
    }
    // One large ground slab collider under the whole city (roads sit at y = 0).
    this.physics.fixedCuboid(new THREE.Vector3(0, -2, 0), new THREE.Vector3(3000, 2, 3000), new THREE.Quaternion());
  }

  /** Invisible walls keep the fight inside the city (the HUD warns before they are reached). */
  private buildBoundary() {
    const b = TUNING.city.boundary + 40;
    const h = TUNING.city.ceiling + 200;
    const q = new THREE.Quaternion();
    const wall = (c: THREE.Vector3, half: THREE.Vector3) => this.physics.fixedCuboid(c, half, q, G.BOUNDARY, G.PLAYER);
    wall(new THREE.Vector3(b, h / 2, 0), new THREE.Vector3(5, h, b + 10));
    wall(new THREE.Vector3(-b, h / 2, 0), new THREE.Vector3(5, h, b + 10));
    wall(new THREE.Vector3(0, h / 2, b), new THREE.Vector3(b + 10, h, 5));
    wall(new THREE.Vector3(0, h / 2, -b), new THREE.Vector3(b + 10, h, 5));
    wall(new THREE.Vector3(0, TUNING.city.ceiling + 60, 0), new THREE.Vector3(b + 10, 5, b + 10));
  }

  /** Is this point inside (or very near) a building volume? */
  insideBuilding(p: THREE.Vector3, margin = 0): boolean {
    for (const b of this.buildings) {
      if (
        p.x > b.box.min.x - margin && p.x < b.box.max.x + margin &&
        p.y > b.box.min.y - margin && p.y < b.box.max.y + margin &&
        p.z > b.box.min.z - margin && p.z < b.box.max.z + margin
      )
        return true;
    }
    return false;
  }
}

const _v = new THREE.Vector3();
