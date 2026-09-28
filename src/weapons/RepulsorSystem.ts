import * as THREE from 'three';
import type { GameContext } from '../game/Context';
import { TUNING } from '../game/constants';
import { G } from '../physics/Physics';
import type { Side } from '../player/PlayerVisual';

const R = TUNING.repulsor;
const MASK = G.WORLD | G.ENEMY | G.SHIELD | G.ENEMY_MISSILE | G.DEBRIS;
const IMPACT = new THREE.Color(1.2, 2.6, 3.4);
const _origin = new THREE.Vector3();
const _dir = new THREE.Vector3();
const _end = new THREE.Vector3();

/**
 * Palm repulsors: alternating hitscan energy blasts fired from the actual palm reactors toward
 * the point under the crosshair (Rapier raycast), costing capacitor energy per shot.
 */
export class RepulsorSystem {
  private cooldown = 0;
  private side: Side = 'R';
  private dryTimer = 0;

  constructor(private readonly ctx: GameContext) {}

  reset() {
    this.cooldown = 0;
  }

  update(dt: number) {
    this.cooldown -= dt;
    this.dryTimer -= dt;
    const { player, input } = this.ctx;
    if (!player.alive || !input.button(0) || this.cooldown > 0) return;
    if (!player.spend(TUNING.energy.repulsorCost)) {
      if (this.dryTimer <= 0) {
        this.ctx.audio.dry();
        this.ctx.hud.toast('CAPACITOR LOW', 1, 'warn');
        this.dryTimer = 1.2;
      }
      this.cooldown = 0.2;
      return;
    }
    this.fire(this.side);
    this.side = this.side === 'L' ? 'R' : 'L';
    this.cooldown = R.interval;
  }

  private fire(side: Side) {
    const { player, cam, physics, fx } = this.ctx;
    player.visual.fire(side);
    player.visual.palmWorld(side, _origin);
    _dir.subVectors(cam.aimPoint, _origin).normalize();
    const hit = physics.raycast(_origin, _dir, R.range, MASK, player.collider);
    if (hit) _end.copy(hit.point);
    else _end.copy(_origin).addScaledVector(_dir, R.range);
    fx.beams.fire(_origin, _end);
    fx.muzzle(_origin, 0.9);
    fx.lights.flash(_origin, 0x7fdcff, 220, 18, 0.12);
    cam.kick(0.22);
    this.ctx.audio.repulsor();
    if (!hit) return;
    fx.impact(hit.point, hit.normal, IMPACT, 12, 1.6);
    const owner = hit.owner;
    if (owner) {
      owner.hit({ damage: R.damage, point: hit.point, dir: _dir.clone(), source: 'repulsor', impulse: R.impulse });
      if (owner.kind !== 'destructible') this.ctx.hud.hitMarker();
    } else {
      this.ctx.debris.impulseAt(hit.collider, hit.point, _dir, R.impulse * 3);
    }
  }
}
