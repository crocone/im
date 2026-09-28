import * as THREE from 'three';
import type { GameContext } from '../game/Context';
import { interceptTime, rand } from '../game/math';
import type { Boss } from './Boss';

export type AttackKind = 'volley' | 'missiles' | 'stream' | 'dash' | 'blast';

const BOLT = 150;
const _v = new THREE.Vector3();
const _aim = new THREE.Vector3();
const CHARGE = new THREE.Color(3.5, 1.2, 0.4);

/** Boss attack patterns and their scheduling per phase. */
export class BossAttacks {
  current: AttackKind | null = null;
  /** 0..1 charge glow for telegraphs */
  charge = 0;
  private t = 0;
  private cooldown = 3.5;
  private shots = 0;
  private shotTimer = 0;
  private arm = 0;
  private step = 0;
  private dashHit = false;
  private last: AttackKind | null = null;
  readonly dashDir = new THREE.Vector3();

  constructor(private readonly ctx: GameContext, private readonly boss: Boss) {}

  reset() {
    this.current = null;
    this.cooldown = 3.5;
    this.charge = 0;
  }

  get dashing() {
    return this.current === 'dash' && this.step === 1;
  }

  get rooted() {
    return (this.current === 'dash' && this.step !== 1) || this.current === 'blast';
  }

  update(dt: number) {
    const phase = this.boss.phase;
    const critical = phase === 'critical';
    if (!this.current) {
      this.charge = Math.max(0, this.charge - dt * 2);
      this.cooldown -= dt * (critical ? 1.7 : 1);
      if (this.cooldown <= 0 && this.ctx.player.alive) this.start(this.choose());
      return;
    }
    this.t += dt;
    switch (this.current) {
      case 'volley':
        this.ripple(dt, 0.09, 0.04, 9, 1.8, (n) => (n === 6 ? 0.7 : 0.09));
        break;
      case 'stream':
        this.ripple(dt, 0.075, 0.02, 7, 1.4, () => 0.075);
        break;
      case 'missiles':
        this.shotTimer -= dt;
        if (this.shots > 0 && this.shotTimer <= 0) {
          this.missile();
          this.shots--;
          this.shotTimer = 0.17;
        }
        if (this.shots === 0 && this.t > 0.6) this.finish();
        break;
      case 'dash':
        this.dash(dt);
        break;
      case 'blast':
        this.blast(dt);
        break;
    }
  }

  private choose(): AttackKind {
    const phase = this.boss.phase;
    const pool: AttackKind[] = phase === 'shielded'
      ? ['volley', 'missiles', 'volley', 'missiles']
      : phase === 'exposed'
        ? ['volley', 'missiles', 'stream', 'dash', 'blast', 'missiles']
        : ['stream', 'missiles', 'dash', 'blast', 'dash', 'volley'];
    let pick = pool[Math.floor(Math.random() * pool.length)];
    if (pick === this.last) pick = pool[(pool.indexOf(pick) + 1) % pool.length];
    return pick;
  }

  private start(kind: AttackKind) {
    this.current = kind;
    this.last = kind;
    this.t = 0;
    this.step = 0;
    this.shotTimer = 0.25;
    const phase = this.boss.phase;
    if (kind === 'volley') this.shots = 12;
    if (kind === 'stream') this.shots = 18;
    if (kind === 'missiles') this.shots = phase === 'shielded' ? 4 : 8;
    if (kind === 'dash') {
      this.dashHit = false;
      this.ctx.hud.toast('WARNING — BEHEMOTH CHARGING', 1.6, 'danger');
      this.ctx.audio.bossCharge();
    }
    if (kind === 'blast') {
      this.ctx.hud.toast('WARNING — AREA BLAST, GET CLEAR', 1.8, 'danger');
      this.ctx.audio.bossCharge();
    }
  }

  private finish() {
    this.current = null;
    const phase = this.boss.phase;
    this.cooldown = phase === 'shielded' ? rand(2.8, 3.8) : phase === 'exposed' ? rand(2.0, 2.8) : rand(1.6, 2.2);
  }

  private ripple(dt: number, _interval: number, spread: number, damage: number, size: number, next: (left: number) => number) {
    this.shotTimer -= dt;
    this.charge = Math.min(1, this.charge + dt * 3);
    if (this.shots > 0 && this.shotTimer <= 0) {
      const muzzle = this.boss.muzzle(this.arm++ % 2 === 0 ? 'L' : 'R', _v);
      const player = this.ctx.player;
      const t = interceptTime(muzzle, player.position, player.flight.vel, BOLT);
      _aim.copy(player.position).addScaledVector(player.flight.vel, t);
      const dir = _aim.sub(muzzle).normalize();
      dir.x += rand(-spread, spread);
      dir.y += rand(-spread, spread);
      dir.z += rand(-spread, spread);
      dir.normalize();
      this.ctx.bolts.fire(muzzle, dir.multiplyScalar(BOLT), damage, size);
      this.ctx.fx.muzzle(muzzle, 2.5, CHARGE);
      this.ctx.audio.enemyShot(muzzle, 0.6);
      this.shots--;
      this.shotTimer = next(this.shots);
    }
    if (this.shots === 0) this.finish();
  }

  private missile() {
    const side = this.arm++ % 2 === 0 ? 'L' : 'R';
    const pos = this.boss.rackMuzzle(side, new THREE.Vector3());
    const out = side === 'L' ? 1 : -1;
    const dir = this.boss.localDir(new THREE.Vector3(out * rand(0.3, 0.6), rand(0.8, 1.1), rand(0.2, 0.5))).normalize();
    this.ctx.missiles.fireHostile(pos, dir, 30);
  }

  private dash(dt: number) {
    const player = this.ctx.player;
    if (this.step === 0) {
      this.charge = Math.min(1, this.t / 1.0);
      if (this.t > 1.05) {
        _aim.copy(player.position).addScaledVector(player.flight.vel, 0.35);
        this.dashDir.subVectors(_aim, this.boss.position).normalize();
        this.step = 1;
        this.t = 0;
        this.ctx.audio.bossDash();
      }
    } else if (this.step === 1) {
      const d = this.boss.position.distanceTo(player.position);
      if (!this.dashHit && d < 9) {
        this.dashHit = true;
        player.hit({ damage: 30, point: player.position.clone(), dir: this.dashDir.clone(), source: 'enemy', impulse: 0 });
        player.flight.vel.addScaledVector(this.dashDir, 45);
        this.ctx.cam.shake(0.9);
      }
      _v.subVectors(player.position, this.boss.position);
      if (this.t > 1.3 || (this.t > 0.3 && _v.dot(this.dashDir) < -5)) {
        this.step = 2;
        this.t = 0;
      }
    } else {
      this.charge = Math.max(0, this.charge - dt * 2);
      if (this.t > 0.9) this.finish();
    }
  }

  private blast(dt: number) {
    if (this.step === 0) {
      this.charge = Math.min(1, this.t / 1.6);
      // energy drawn into the core
      for (let i = 0; i < 3; i++) {
        _v.set(rand(-1, 1), rand(-1, 1), rand(-1, 1)).normalize().multiplyScalar(rand(8, 14));
        const p = this.boss.position.clone().add(_v);
        this.ctx.fx.glow.emit({ pos: p, vel: _v.clone().multiplyScalar(-2.2), life: 0.45, size: 0.8, size1: 0.2,
          color: CHARGE, alpha: 1, alpha1: 0.3 });
      }
      if (Math.floor(this.t * 3) !== Math.floor((this.t - dt) * 3))
        this.ctx.fx.rings.emit({ pos: this.boss.position, life: 0.5, size: 30, size1: 6, color: CHARGE, alpha: 0.6, alpha1: 0 });
      if (this.t > 1.6) {
        this.step = 1;
        this.t = 0;
        this.charge = 0;
        this.ctx.combat.explosion(this.boss.position, { radius: 48, damage: 34, scale: 4.5, source: 'enemy', shockwave: true });
        this.ctx.fx.rings.emit({ pos: this.boss.position, life: 0.7, size: 10, size1: 110, color: CHARGE, alpha: 1, alpha1: 0 });
      }
    } else if (this.t > 0.8) this.finish();
  }
}
