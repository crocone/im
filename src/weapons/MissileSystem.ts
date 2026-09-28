import * as THREE from 'three';
import type { MissileTarget } from '../enemies/Enemy';
import type { GameContext } from '../game/Context';
import type { Side } from '../player/PlayerVisual';
import { MissilePool } from './Missile';

const _pos = new THREE.Vector3();
const _dir = new THREE.Vector3();
const _f = new THREE.Vector3();
const _r = new THREE.Vector3();
const _u = new THREE.Vector3();

/**
 * Homing missiles from the back-mounted rails (requires a lock) plus the pool of hostile
 * missiles fired by turrets and the boss.
 */
export class MissileSystem {
  readonly homing: MissilePool;
  readonly hostile: MissilePool;
  private side: Side = 'L';
  private cooldown = 0;

  constructor(private readonly ctx: GameContext) {
    const template = ctx.assets.scene('missile');
    this.homing = new MissilePool(ctx, 'homing', template, 12);
    const red = template.clone(true);
    red.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh && (m.material as THREE.Material).name === 'Munition_White') {
        const mat = (m.material as THREE.MeshStandardMaterial).clone();
        mat.color.setRGB(0.35, 0.06, 0.05);
        m.material = mat;
      }
    });
    this.hostile = new MissilePool(ctx, 'enemy', red, 48);
  }

  reset() {
    this.homing.clear();
    this.hostile.clear();
    this.cooldown = 0;
  }

  update(dt: number) {
    this.cooldown -= dt;
    const { player, input, targeting, hud } = this.ctx;
    if (player.alive && input.justPressed('Digit1') && this.cooldown <= 0) {
      if (!targeting.locked) {
        hud.toast('NO LOCK — HOLD RMB ON A TARGET', 1.4, 'warn');
        this.ctx.audio.dry();
      } else if (player.missiles <= 0) {
        hud.toast('MISSILES DEPLETED', 1.2, 'warn');
        this.ctx.audio.dry();
      } else {
        this.launch(targeting.current!);
      }
    }
    this.homing.update(dt);
    this.hostile.update(dt);
  }

  private launch(target: MissileTarget) {
    const m = this.homing.acquire();
    if (!m) return;
    const { player } = this.ctx;
    player.missiles--;
    this.cooldown = 0.28;
    player.visual.launcher[this.side].getWorldPosition(_pos);
    player.flight.forward(_f);
    player.flight.right(_r);
    player.flight.up(_u);
    // leave the rail up and outward, then arc onto the target
    const out = this.side === 'L' ? -1 : 1;
    _dir.copy(_u).multiplyScalar(0.9).addScaledVector(_r, 0.6 * out).addScaledVector(_f, 0.35).normalize();
    m.launch(_pos, _dir, 16, player.flight.vel, target);
    this.side = this.side === 'L' ? 'R' : 'L';
    this.ctx.audio.missileLaunch();
    this.ctx.cam.kick(0.35);
  }

  /** Fire a hostile missile (turrets / boss). */
  fireHostile(pos: THREE.Vector3, dir: THREE.Vector3, speed: number) {
    const m = this.hostile.acquire();
    if (!m) return;
    m.launch(pos, dir, speed, new THREE.Vector3(), this.ctx.player);
    this.ctx.audio.enemyMissile(pos);
  }

  /** Active hostile missiles (HUD markers, radar). */
  incoming() {
    return this.hostile.items.filter((m) => m.active);
  }
}
