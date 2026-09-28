import * as THREE from 'three';
import type { GameContext } from '../game/Context';
import { ShieldMaterial } from '../fx/ShieldMaterial';
import type { HitInfo, Hittable, RAPIER } from '../physics/Physics';

const SHIELD_SPARK = new THREE.Color(1.2, 2.2, 4);
const _local = new THREE.Vector3();

/**
 * The boss's energy shield. A separate mesh + collider: repulsor fire only ripples across it,
 * missiles drain it. When it collapses it flashes, dissolves and disappears.
 */
export class BossShield implements Hittable {
  readonly kind = 'shield' as const;
  readonly max = 900;
  hp = this.max;
  active = true;
  readonly material = new ShieldMaterial();
  private breakT = -1;
  private hintTimer = 0;
  onBreak: (() => void) | null = null;

  constructor(private readonly ctx: GameContext, readonly mesh: THREE.Mesh, readonly collider: RAPIER.Collider) {
    mesh.material = this.material;
    mesh.renderOrder = 15;
    mesh.castShadow = false;
    mesh.receiveShadow = false;
    ctx.physics.register(collider, this);
  }

  get fraction() {
    return this.active ? this.hp / this.max : 0;
  }

  hit(info: HitInfo) {
    if (!this.active) return;
    _local.copy(info.point);
    this.mesh.worldToLocal(_local).normalize();
    const explosive = info.source === 'missile' || info.source === 'mini';
    this.material.impact(_local, explosive ? 1 : 0.35);
    this.ctx.fx.impact(info.point, _local.copy(info.point).sub(this.mesh.getWorldPosition(new THREE.Vector3())).normalize(),
      SHIELD_SPARK, explosive ? 26 : 8, explosive ? 4 : 1.8);
    this.ctx.audio.shieldHit(explosive);
    if (!explosive) {
      this.hintTimer -= 1;
      if (this.hintTimer <= 0) {
        this.ctx.hud.toast('SHIELD DEFLECTING REPULSORS — USE MISSILES', 2, 'warn');
        this.hintTimer = 25;
      }
      return;
    }
    this.hp -= info.damage;
    this.ctx.hud.hitMarker();
    this.ctx.score.bossDamage(info.damage * 0.5, info.point);
    if (this.hp <= 0) this.collapse();
  }

  private collapse() {
    this.hp = 0;
    this.active = false;
    this.collider.setEnabled(false);
    this.breakT = 0;
    const p = this.mesh.getWorldPosition(new THREE.Vector3());
    this.ctx.fx.explosions.spawn(p, { scale: 3.5, shockwave: true, smoke: 4, sparks: 80, tint: new THREE.Color(0.5, 0.9, 2.2) });
    this.ctx.fx.rings.emit({ pos: p, life: 0.8, size: 8, size1: 70, color: new THREE.Color(0.6, 1.2, 2.6), alpha: 1, alpha1: 0 });
    this.ctx.cam.shake(0.8);
    this.ctx.audio.shieldBreak();
    this.onBreak?.();
  }

  update(dt: number) {
    this.material.tick(dt);
    this.material.uniforms.uStrength.value = this.fraction;
    if (this.breakT >= 0) {
      this.breakT += dt;
      this.material.uniforms.uBreak.value = Math.min(1, this.breakT / 1.3);
      this.mesh.scale.setScalar(1 + this.breakT * 0.25);
      if (this.breakT > 1.4) {
        this.mesh.visible = false;
        this.breakT = -1;
      }
    }
  }
}
