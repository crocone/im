import * as THREE from 'three';
import type { Enemy } from '../enemies/Enemy';
import type { GameContext } from '../game/Context';
import { TUNING } from '../game/constants';

export type LockState = 'idle' | 'searching' | 'acquiring' | 'locked';

const L = TUNING.lock;
const _d = new THREE.Vector3();

/**
 * Lock-on computer. Holding RMB acquires the enemy nearest the crosshair; acquisition takes
 * time and only progresses while the target stays inside the lock cone with line of sight.
 * Drifting off target bleeds progress; leaving the break cone, range or sight cancels the lock.
 */
export class TargetingSystem {
  current: Enemy | null = null;
  progress = 0;
  state: LockState = 'idle';
  private losLost = 0;
  private beepTimer = 0;

  constructor(private readonly ctx: GameContext) {}

  reset() {
    this.current = null;
    this.progress = 0;
    this.state = 'idle';
  }

  get locked() {
    return this.state === 'locked' && this.current !== null && this.current.alive;
  }

  /** Angle between the aim direction and a world position. */
  angleTo(pos: THREE.Vector3) {
    _d.subVectors(pos, this.ctx.camera.position).normalize();
    return Math.acos(Math.max(-1, Math.min(1, _d.dot(this.ctx.cam.aimDir))));
  }

  private inRange(e: Enemy) {
    return e.position.distanceTo(this.ctx.player.position) < L.range;
  }

  candidates(cone: number, range: number): Enemy[] {
    const out: { e: Enemy; a: number }[] = [];
    for (const e of this.ctx.enemies.list) {
      if (!e.lockable) continue;
      if (e.position.distanceTo(this.ctx.player.position) > range) continue;
      const a = this.angleTo(e.position);
      if (a < cone) out.push({ e, a });
    }
    out.sort((x, y) => x.a - y.a);
    return out.map((o) => o.e);
  }

  private visible(e: Enemy) {
    return this.ctx.physics.lineOfSight(this.ctx.camera.position, e.position);
  }

  private drop(message?: string) {
    if (message && this.state === 'locked') this.ctx.hud.toast(message, 1.4, 'warn');
    this.current = null;
    this.progress = 0;
  }

  update(dt: number) {
    const { input } = this.ctx;
    const holding = input.button(2) && this.ctx.player.alive;
    const cur = this.current;
    if (cur) {
      const a = this.angleTo(cur.position);
      this.losLost = this.visible(cur) ? 0 : this.losLost + dt;
      if (!cur.alive) this.drop();
      else if (!cur.lockable || !this.inRange(cur)) this.drop('TARGET LOST');
      else if (a > L.breakCone) this.drop('LOCK BROKEN');
      else if (this.losLost > 1.2) this.drop('LOCK BROKEN — NO LINE OF SIGHT');
    }
    if (input.justPressed('Tab')) {
      const list = this.candidates(L.miniCone, L.range);
      if (list.length) {
        const idx = this.current ? list.indexOf(this.current) : -1;
        this.current = list[(idx + 1) % list.length];
        this.progress = 0;
        this.state = 'acquiring';
        this.ctx.audio.beep(0.6);
      }
    }
    if (holding) {
      if (!this.current) {
        const best = this.candidates(L.cone, L.range).find((e) => this.visible(e));
        if (best) {
          this.current = best;
          this.progress = 0;
        }
      }
      if (this.current && this.state !== 'locked') {
        const a = this.angleTo(this.current.position);
        const ok = a < L.cone && this.losLost === 0;
        this.progress += ok ? dt / this.current.lockTime : -dt * 0.6;
        if (this.progress <= 0) this.progress = 0;
        if (this.progress >= 1) {
          this.progress = 1;
          this.state = 'locked';
          this.ctx.hud.toast(`TARGET LOCKED — ${this.current.label}`, 1.4, 'danger');
          this.ctx.audio.lockTone();
        }
      }
    } else if (this.current && this.state !== 'locked') {
      this.progress -= dt * 0.8;
      if (this.progress <= 0) this.drop();
    }
    if (!this.current) this.state = holding ? 'searching' : 'idle';
    else if (this.state !== 'locked') this.state = 'acquiring';
    // acquisition beeps speed up as the lock builds
    if (this.state === 'acquiring') {
      this.beepTimer -= dt;
      if (this.beepTimer <= 0) {
        this.ctx.audio.beep(0.35 + this.progress * 0.5);
        this.beepTimer = 0.28 - this.progress * 0.2;
      }
    }
  }

  /** Targets for a mini-missile salvo: the locked target first, then others in a wide cone. */
  salvoTargets(max: number): Enemy[] {
    const list = this.candidates(L.miniCone, L.miniRange).filter((e) => this.visible(e));
    if (this.current && this.current.alive) {
      const i = list.indexOf(this.current);
      if (i > 0) list.splice(i, 1);
      if (i !== 0) list.unshift(this.current);
    }
    return list.slice(0, max);
  }
}
