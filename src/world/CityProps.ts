import * as THREE from 'three';
import type { AssetKey, Assets } from '../game/Assets';
import { TUNING } from '../game/constants';
import type { Physics } from '../physics/Physics';
import type { CityBuilder } from './CityBuilder';
import { InstancedKit } from './InstancedKit';

export type DestructibleKind = 'column' | 'sign' | 'waterTower' | 'smallHouse';

export interface DestructibleSpot {
  kind: DestructibleKind;
  pos: THREE.Vector3;
  yaw: number;
}

/** Simple collision proxies per prop (local space, before yaw): boxes (half extents) or vertical cylinders. */
type Proxy = { box: [number, number, number]; y: number } | { cyl: [number, number]; y: number };
const PROXIES: Partial<Record<AssetKey, Proxy>> = {
  car: { box: [0.9, 0.72, 2.3], y: 0.72 },
  barrier: { box: [0.33, 0.42, 1.5], y: 0.42 },
  streetLamp: { cyl: [0.16, 3.7], y: 3.7 },
  tree: { cyl: [0.28, 1.7], y: 1.7 },
  rooftopHvac: { box: [1.6, 1.0, 1.1], y: 1.0 },
  rooftopVent: { cyl: [0.7, 1.15], y: 1.15 },
  antenna: { cyl: [0.7, 7.2], y: 7.2 },
};

const CAR_COLORS = [0xd8d8d4, 0x9ea3a8, 0x1a1c20, 0x8c1c16, 0x1f3f7a, 0xd9a21b, 0x24452e, 0x5b2f6b].map(
  (c) => new THREE.Color(c),
);

/** Street furniture, rooftop equipment and the placement of destructible props. */
export class CityProps {
  readonly destructibles: DestructibleSpot[] = [];
  private readonly kits = new Map<string, InstancedKit>();
  private readonly m = new THREE.Matrix4();
  private readonly q = new THREE.Quaternion();
  private readonly one = new THREE.Vector3(1, 1, 1);
  private readonly up = new THREE.Vector3(0, 1, 0);

  constructor(
    private readonly scene: THREE.Scene,
    private readonly assets: Assets,
    private readonly city: CityBuilder,
    private readonly physics: Physics,
  ) {}

  private kit(key: AssetKey, capacity: number, shadow = false) {
    let k = this.kits.get(key);
    if (!k) {
      k = new InstancedKit(this.assets.scene(key), capacity, shadow, true);
      this.kits.set(key, k);
    }
    return k;
  }

  private place(key: AssetKey, x: number, y: number, z: number, yaw: number, scale = 1, color?: THREE.Color) {
    this.q.setFromAxisAngle(this.up, yaw);
    const s = scale === 1 ? this.one : _s.set(scale, scale, scale);
    this.m.compose(_p.set(x, y, z), this.q, s);
    this.kit(key, 2000, key === 'tree' || key === 'antenna').add(this.m, color, 'Car_Paint');
    const proxy = PROXIES[key];
    if (proxy) {
      _c.set(x, y + proxy.y * scale, z);
      if ('box' in proxy) this.physics.fixedCuboid(_c, _h.set(...proxy.box).multiplyScalar(scale), this.q);
      else this.physics.fixedCylinder(_c, proxy.cyl[0] * scale, proxy.cyl[1] * scale);
    }
  }

  build(rnd: () => number) {
    const n = TUNING.city.blocks;
    const pitch = TUNING.city.pitch;
    const half = (n * pitch) / 2;
    // street lamps: three per block side, arms reaching over the road
    const sides: [number, number, number][] = [[-42.3, 0, 0], [42.3, 0, Math.PI], [0, -42.3, -Math.PI / 2], [0, 42.3, Math.PI / 2]];
    for (const b of this.city.blocks) {
      for (const [ox, oz, yaw] of sides) {
        for (const t of [-24, 24]) {
          const along = ox === 0 ? [t, 0] : [0, t];
          this.place('streetLamp', b.x + ox + along[0], 0.2, b.z + oz + along[1], yaw);
        }
      }
    }
    // traffic: parked / abandoned cars along the carriageways
    for (let k = 0; k <= n; k++) {
      const line = -half + k * pitch;
      for (let s = 0; s < n; s++) {
        const mid = -half + pitch / 2 + s * pitch;
        for (const horizontal of [true, false]) {
          const cars = Math.floor(rnd() * 3.2);
          for (let c = 0; c < cars; c++) {
            const lane = [-5.25, -1.75, 1.75, 5.25][Math.floor(rnd() * 4)];
            const along = (rnd() - 0.5) * 70;
            const dir = lane > 0 ? 0 : Math.PI;
            const crashed = rnd() < 0.12;
            const yaw = (horizontal ? Math.PI / 2 : 0) + dir + (crashed ? (rnd() - 0.5) * 2.4 : (rnd() - 0.5) * 0.12);
            const color = CAR_COLORS[Math.floor(rnd() * CAR_COLORS.length)];
            if (horizontal) this.place('car', mid + along, 0, line + lane, yaw, 1, color);
            else this.place('car', line + lane, 0, mid + along, yaw, 1, color);
          }
        }
      }
    }
    // roadblocks at a few junctions
    for (let r = 0; r < 14; r++) {
      const jx = -half + Math.floor(1 + rnd() * (n - 1)) * pitch;
      const jz = -half + Math.floor(1 + rnd() * (n - 1)) * pitch;
      const alongX = rnd() < 0.5;
      for (let b = -2; b <= 2; b++) {
        const off = b * 3.1;
        if (alongX) this.place('barrier', jx + 13, 0, jz + off, 0);
        else this.place('barrier', jx + off, 0, jz + 13, Math.PI / 2);
      }
    }
    for (const b of this.city.blocks) this.decorateBlock(b.kind, b.x, b.z, rnd, b.lots);
    this.rooftops(rnd);
    for (const k of this.kits.values()) {
      k.finish();
      k.addTo(this.scene);
    }
  }

  private decorateBlock(kind: string, bx: number, bz: number, rnd: () => number,
    lots: { x: number; z: number; lot: { use: string } }[]) {
    if (kind === 'park') {
      for (const hx of [-22, 22])
        for (const hz of [-24, 0, 24]) {
          this.destructibles.push({ kind: 'smallHouse', pos: new THREE.Vector3(bx + hx, 0.2, bz + hz), yaw: Math.floor(rnd() * 4) * (Math.PI / 2) });
        }
      for (let t = 0; t < 14; t++) {
        const x = bx + (rnd() - 0.5) * 72;
        const z = bz + (rnd() - 0.5) * 72;
        if (Math.abs(Math.abs(x - bx) - 22) < 6.5 && Math.abs(z - bz) < 31) continue;
        this.place('tree', x, 0.2, z, rnd() * Math.PI * 2, 0.8 + rnd() * 0.6);
      }
      this.destructibles.push({ kind: 'sign', pos: new THREE.Vector3(bx, 0.2, bz - 37), yaw: Math.PI });
      return;
    }
    if (kind === 'plaza') {
      for (let c = 0; c < 6; c++)
        for (const z of [-9, 9])
          this.destructibles.push({ kind: 'column', pos: new THREE.Vector3(bx - 25 + c * 10, 0.2, bz + z), yaw: 0 });
      for (const [tx, tz] of [[-30, -30], [30, -30], [-30, 30], [30, 30], [0, -28], [0, 28]])
        this.place('tree', bx + tx, 0.2, bz + tz, rnd() * 6, 1.0 + rnd() * 0.3);
      this.destructibles.push({ kind: 'sign', pos: new THREE.Vector3(bx - 37, 0.2, bz), yaw: -Math.PI / 2 });
      this.destructibles.push({ kind: 'sign', pos: new THREE.Vector3(bx + 37, 0.2, bz), yaw: Math.PI / 2 });
      return;
    }
    for (const lot of lots) {
      if (lot.lot.use === 'plaza') {
        for (let c = 0; c < 4; c++)
          for (const z of [-7, 7])
            this.destructibles.push({ kind: 'column', pos: new THREE.Vector3(lot.x - 12 + c * 8, 0.2, lot.z + z), yaw: 0 });
        this.place('tree', lot.x - 14, 0.2, lot.z - 15, 1, 1.2);
        this.place('tree', lot.x + 14, 0.2, lot.z + 15, 2, 1.1);
      } else if (lot.lot.use === 'parking') {
        for (let r = 0; r < 3; r++)
          for (let c = 0; c < 6; c++)
            if (rnd() < 0.7)
              this.place('car', lot.x - 13 + c * 5.2, 0.2, lot.z - 10 + r * 10, (r % 2) * Math.PI + (rnd() - 0.5) * 0.1, 1,
                CAR_COLORS[Math.floor(rnd() * CAR_COLORS.length)]);
      }
    }
    // billboards facing the street on some block edges
    if (kind === 'dense' && rnd() < 0.35) {
      const side = Math.floor(rnd() * 4);
      const t = rnd() < 0.5 ? -20 : 20;
      const spots: [number, number, number][] = [[-39.3, t, -Math.PI / 2], [39.3, t, Math.PI / 2], [t, -39.3, Math.PI], [t, 39.3, 0]];
      const [ox, oz, yaw] = spots[side];
      this.destructibles.push({ kind: 'sign', pos: new THREE.Vector3(bx + ox, 0.2, bz + oz), yaw });
    }
  }

  private rooftops(rnd: () => number) {
    const waterTowerTypes = new Set([4, 6, 8, 9]);
    const hasTower = new Set<number>();
    for (const a of this.city.anchors) {
      if (a.kind === 'Top') {
        this.place('antenna', a.pos.x, a.pos.y, a.pos.z, rnd() * Math.PI * 2);
        a.used = true;
      } else if (a.kind === 'Small') {
        this.place(rnd() < 0.6 ? 'rooftopHvac' : 'rooftopVent', a.pos.x, a.pos.y, a.pos.z, Math.floor(rnd() * 4) * (Math.PI / 2));
        a.used = true;
      } else if (a.kind === 'Roof') {
        if (waterTowerTypes.has(a.buildingType) && !hasTower.has(a.building) && rnd() < 0.6) {
          this.destructibles.push({ kind: 'waterTower', pos: a.pos.clone(), yaw: rnd() * Math.PI * 2 });
          hasTower.add(a.building);
          a.used = true;
        } else if (rnd() < 0.3) {
          this.place('rooftopHvac', a.pos.x, a.pos.y, a.pos.z, Math.floor(rnd() * 4) * (Math.PI / 2));
          a.used = true;
        }
      }
    }
  }
}

const _p = new THREE.Vector3();
const _s = new THREE.Vector3();
const _c = new THREE.Vector3();
const _h = new THREE.Vector3();
