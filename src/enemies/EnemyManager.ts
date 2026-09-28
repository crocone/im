import * as THREE from 'three';
import type { GameContext } from '../game/Context';
import { TUNING } from '../game/constants';
import { rand } from '../game/math';
import type { MarkerInfo } from '../hud/TargetMarkers';
import type { Anchor } from '../world/CityBuilder';
import type { Blip } from '../hud/Radar';
import { Boss } from './Boss';
import { Drone } from './Drone';
import type { Enemy } from './Enemy';
import { Turret } from './Turret';

/** Owns every live enemy: spawning, per-frame updates, cleanup and HUD/radar summaries. */
export class EnemyManager {
  readonly list: Enemy[] = [];
  boss: Boss | null = null;
  private readonly markers: MarkerInfo[] = [];
  private readonly markerOf = new Map<object, MarkerInfo>();
  private readonly turretAnchors: Anchor[] = [];
  private readonly attackers = new Set<Enemy>();

  constructor(private readonly ctx: GameContext) {}

  /** Enemies that still count toward clearing the wave. */
  get hostiles() {
    return this.list.filter((e) => e.alive).length;
  }

  /** Limit how many drones fire at the same time (fairness / readability). */
  takeAttackSlot(e: Enemy) {
    const wave = this.ctx.waves.wave;
    const max = this.boss ? 2 : wave <= 2 ? 2 : 3;
    if (this.attackers.has(e)) return true;
    if (this.attackers.size >= max) return false;
    this.attackers.add(e);
    return true;
  }

  releaseAttackSlot(e: Enemy) {
    this.attackers.delete(e);
  }

  spawnDrone(pos: THREE.Vector3, aggression = 1) {
    const d = new Drone(this.ctx, pos, aggression);
    this.list.push(d);
    return d;
  }

  /** Drones entering from a random direction outside the player's view bubble. */
  spawnDroneWave(count: number, aggression: number) {
    const p = this.ctx.player.position;
    const base = rand(0, Math.PI * 2);
    for (let i = 0; i < count; i++) {
      const a = base + (i / count) * Math.PI * 1.2 + rand(-0.2, 0.2);
      const r = rand(260, 360);
      const b = TUNING.city.boundary - 30;
      const pos = new THREE.Vector3(
        THREE.MathUtils.clamp(p.x + Math.cos(a) * r, -b, b),
        rand(90, 170),
        THREE.MathUtils.clamp(p.z + Math.sin(a) * r, -b, b),
      );
      this.spawnDrone(pos, aggression);
    }
  }

  spawnEscort(from: THREE.Vector3, count: number) {
    for (let i = 0; i < count; i++)
      this.spawnDrone(from.clone().add(new THREE.Vector3(rand(-12, 12), rand(4, 10), rand(-12, 12))), 1.2);
  }

  /** Deploy turrets on free rooftop anchors at a useful distance from the player. */
  spawnTurrets(count: number) {
    const p = this.ctx.player.position;
    const used: THREE.Vector3[] = this.list.filter((e) => e.kind === 'turret' && e.alive).map((e) => e.position);
    const options = this.ctx.city.anchors
      .filter((a) => a.kind === 'Roof' && !a.used)
      .map((a) => ({ a, d: Math.hypot(a.pos.x - p.x, a.pos.z - p.z) }))
      .filter((o) => o.d > 110 && o.d < 380)
      .sort(() => Math.random() - 0.5);
    let placed = 0;
    for (const { a } of options) {
      if (placed >= count) break;
      if (used.some((u) => u.distanceTo(a.pos) < 70)) continue;
      a.used = true;
      this.turretAnchors.push(a);
      used.push(a.pos);
      this.list.push(new Turret(this.ctx, a.pos, rand(0, Math.PI * 2)));
      placed++;
    }
    return placed;
  }

  spawnBoss() {
    const p = this.ctx.player.position;
    const a = rand(0, Math.PI * 2);
    const spawn = new THREE.Vector3(p.x + Math.cos(a) * 220, 330, p.z + Math.sin(a) * 220);
    const b = TUNING.city.boundary - 80;
    spawn.x = THREE.MathUtils.clamp(spawn.x, -b, b);
    spawn.z = THREE.MathUtils.clamp(spawn.z, -b, b);
    this.boss = new Boss(this.ctx, spawn);
    this.list.push(this.boss);
    return this.boss;
  }

  update(dt: number) {
    for (const e of this.list) e.update(dt);
    for (let i = this.list.length - 1; i >= 0; i--) {
      const e = this.list[i];
      if (e.removed) {
        e.dispose();
        this.list.splice(i, 1);
        this.markerOf.delete(e);
        this.attackers.delete(e);
        if (e === this.boss) this.boss = null;
      }
    }
  }

  clear() {
    for (const e of this.list) e.dispose();
    this.list.length = 0;
    this.boss = null;
    this.markerOf.clear();
    this.attackers.clear();
    for (const a of this.turretAnchors) a.used = false;
    this.turretAnchors.length = 0;
  }

  /** Marker info for the HUD (enemies + incoming missiles), reusing objects between frames. */
  markerInfo(): MarkerInfo[] {
    this.markers.length = 0;
    for (const e of this.list) {
      if (!e.lockable) continue;
      let m = this.markerOf.get(e);
      if (!m) {
        m = { position: e.position, kind: 'enemy', label: e.label, scale: e.kind === 'boss' ? 3 : e.kind === 'turret' ? 1.4 : 1 };
        this.markerOf.set(e, m);
      }
      this.markers.push(m);
    }
    for (const msl of this.ctx.missiles.incoming()) {
      let m = this.markerOf.get(msl);
      if (!m) {
        m = { position: msl.position, kind: 'missile', label: 'MSL', scale: 0.6 };
        this.markerOf.set(msl, m);
      }
      this.markers.push(m);
    }
    return this.markers;
  }

  markerFor(e: Enemy | null) {
    return e ? this.markerOf.get(e) ?? null : null;
  }

  blips(): Blip[] {
    const out: Blip[] = [];
    for (const e of this.list) if (e.alive) out.push({ position: e.position, kind: e.kind });
    for (const m of this.ctx.missiles.incoming()) out.push({ position: m.position, kind: 'missile' });
    return out;
  }
}
