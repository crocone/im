import * as THREE from 'three';
import type { GameContext } from '../game/Context';
import { TUNING } from '../game/constants';
import { rand } from '../game/math';
import type { Side } from '../player/PlayerVisual';
import { MissilePool } from './Missile';

const _pos = new THREE.Vector3();
const _dir = new THREE.Vector3();
const _f = new THREE.Vector3();
const _r = new THREE.Vector3();
const _u = new THREE.Vector3();

/**
 * Shoulder mini-missile salvo: a rippled volley that fans out from both pods, spreads itself
 * across every valid target in a wide cone (locked target first) and flies independent paths.
 */
export class MiniMissileSystem {
  readonly pool: MissilePool;
  private queue = 0;
  private timer = 0;
  private cooldown = 0;
  private targets: ReturnType<GameContext['targeting']['salvoTargets']> = [];
  private index = 0;

  constructor(private readonly ctx: GameContext) {
    this.pool = new MissilePool(ctx, 'mini', ctx.assets.scene('miniMissile'), 40);
  }

  reset() {
    this.pool.clear();
    this.queue = 0;
    this.cooldown = 0;
  }

  update(dt: number) {
    this.cooldown -= dt;
    const { player, input, hud } = this.ctx;
    if (player.alive && input.justPressed('Digit2') && this.cooldown <= 0 && this.queue === 0) {
      if (player.minis <= 0) {
        hud.toast('MINI-MISSILES DEPLETED', 1.2, 'warn');
        this.ctx.audio.dry();
      } else {
        this.queue = Math.min(TUNING.missiles.salvo, player.minis);
        this.targets = this.ctx.targeting.salvoTargets(this.queue);
        this.index = 0;
        this.timer = 0;
        this.cooldown = 1.2;
        hud.toast(this.targets.length ? `SALVO — ${this.targets.length} TARGET${this.targets.length > 1 ? 'S' : ''}` : 'SALVO — DUMBFIRE', 1.2);
      }
    }
    if (this.queue > 0) {
      this.timer -= dt;
      while (this.queue > 0 && this.timer <= 0) {
        this.fireOne();
        this.timer += 0.07;
      }
    }
    this.pool.update(dt);
  }

  private fireOne() {
    const { player, cam } = this.ctx;
    const m = this.pool.acquire();
    this.queue--;
    if (!m || player.minis <= 0) return;
    player.minis--;
    const side: Side = this.index % 2 === 0 ? 'L' : 'R';
    player.visual.miniLauncher[side].getWorldPosition(_pos);
    player.flight.forward(_f);
    player.flight.right(_r);
    player.flight.up(_u);
    const out = side === 'L' ? -1 : 1;
    _dir.copy(_u).multiplyScalar(rand(0.5, 0.9))
      .addScaledVector(_r, out * rand(0.35, 0.95))
      .addScaledVector(_f, rand(0.2, 0.6))
      .add(new THREE.Vector3(rand(-0.2, 0.2), rand(-0.1, 0.2), rand(-0.2, 0.2)))
      .normalize();
    const target = this.targets.length ? this.targets[this.index % this.targets.length] : null;
    const aim = target ? undefined : cam.aimPoint.clone().add(new THREE.Vector3(rand(-6, 6), rand(-4, 4), rand(-6, 6)));
    m.launch(_pos, _dir, rand(18, 24), player.flight.vel, target, aim);
    this.index++;
    this.ctx.audio.miniLaunch();
    this.ctx.cam.kick(0.08);
  }
}
