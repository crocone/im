import * as THREE from 'three';
import { Assets } from '../game/Assets';
import type { GameContext } from '../game/Context';
import { SCORE, TUNING } from '../game/constants';
import { clamp, damp, quatFromForward, rand, UP } from '../game/math';
import { G, RAPIER, type HitInfo } from '../physics/Physics';
import { ThrusterFlame } from '../fx/ThrusterFlame';
import { BossAttacks } from './BossAttacks';
import { BossShield } from './BossShield';
import { Enemy } from './Enemy';

export type BossPhase = 'intro' | 'shielded' | 'exposed' | 'critical' | 'dying' | 'dead';

const _v = new THREE.Vector3();
const _q = new THREE.Quaternion();
const _look = new THREE.Vector3();
const SPARK = new THREE.Color(4, 2.2, 0.8);

/**
 * Armored Behemoth: multi-phase encounter.
 * shielded  - missile-only shield, energy volleys + missile bursts, repositioning
 * exposed   - shield gone, adds rapid streams, charge dashes and area blasts
 * critical  - below 35 %: faster, shorter cooldowns, burning and sparking
 * dying     - chained explosions, then a huge final blast
 */
export class Boss extends Enemy {
  readonly kind = 'boss' as const;
  readonly label = 'BEHEMOTH';
  phase: BossPhase = 'intro';
  readonly shield: BossShield;
  readonly attacks: BossAttacks;
  onDefeated: (() => void) | null = null;
  private phaseTime = 0;
  private readonly model: THREE.Object3D;
  private readonly arms: THREE.Object3D[];
  private readonly muzzles: Record<'L' | 'R', THREE.Object3D>;
  private readonly racks: Record<'L' | 'R', THREE.Object3D>;
  private readonly coreMats: THREE.MeshStandardMaterial[] = [];
  private readonly flames: ThrusterFlame[] = [];
  private readonly moveTarget = new THREE.Vector3();
  private retarget = 0;
  private escortTimer = 6;
  private fxTimer = 0;
  private readonly facing = new THREE.Quaternion();
  private deathBlasts = 0;

  constructor(ctx: GameContext, spawn: THREE.Vector3) {
    super(ctx, 2600);
    this.lockTime = TUNING.lock.bossTime;
    this.radius = 5.6;
    this.model = ctx.assets.clone('boss');
    this.model.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh) return;
      m.castShadow = true;
      if ((m.material as THREE.Material).name === 'Emissive_Core') {
        m.material = (m.material as THREE.MeshStandardMaterial).clone();
        this.coreMats.push(m.material as THREE.MeshStandardMaterial);
      }
    });
    this.root.add(this.model);
    const n = (name: string) => Assets.node(this.model, name);
    this.arms = [n('Arm_L'), n('Arm_R')];
    this.muzzles = { L: n('Muzzle_Arm_L'), R: n('Muzzle_Arm_R') };
    this.racks = { L: n('RackMuzzle_L'), R: n('RackMuzzle_R') };
    const orange = new THREE.Color(1.0, 0.45, 0.15);
    for (let i = 0; i < 4; i++) this.flames.push(new ThrusterFlame(n(`Thruster_${i}`), 0.32, 3.2, orange, ctx.fx.textures.soft, i));
    for (const s of ['L', 'R']) this.flames.push(new ThrusterFlame(n(`LegThruster_${s}`), 0.3, 2.6, orange, ctx.fx.textures.soft, 7));
    this.position.copy(spawn);
    this.root.position.copy(spawn);
    const shieldMesh = n('Shield') as THREE.Mesh;
    const k = ctx.physics.kinematic(RAPIER.ColliderDesc.ball(3.6), spawn, G.ENEMY, G.PLAYER | G.DEBRIS);
    const shieldCol = ctx.physics.world.createCollider(
      RAPIER.ColliderDesc.ball(5.6).setTranslation(0, shieldMesh.position.y, 0)
        .setCollisionGroups(((G.SHIELD << 16) | G.PLAYER | G.QUERY) >>> 0),
      k.body,
    );
    this.registerBody(k.body, [k.collider]);
    this.colliders.push(shieldCol);
    this.shield = new BossShield(ctx, shieldMesh, shieldCol);
    this.shield.onBreak = () => this.enterPhase('exposed');
    this.attacks = new BossAttacks(ctx, this);
    this.moveTarget.copy(spawn).setY(150);
  }

  get lockable() {
    return this.alive && this.phase !== 'intro';
  }

  get healthFraction() {
    return this.health / this.maxHealth;
  }

  muzzle(side: 'L' | 'R', out: THREE.Vector3) {
    return this.muzzles[side].getWorldPosition(out);
  }

  rackMuzzle(side: 'L' | 'R', out: THREE.Vector3) {
    return this.racks[side].getWorldPosition(out);
  }

  localDir(v: THREE.Vector3) {
    return v.applyQuaternion(this.root.quaternion);
  }

  private enterPhase(p: BossPhase) {
    this.phase = p;
    this.phaseTime = 0;
    const hud = this.ctx.hud;
    if (p === 'shielded') hud.toast('BEHEMOTH SHIELDED — MISSILES ONLY', 2.6, 'warn');
    if (p === 'exposed') {
      hud.banner('SHIELD DOWN', 'HULL EXPOSED — ALL WEAPONS FREE');
      this.ctx.enemies.spawnEscort(this.position, 2);
    }
    if (p === 'critical') hud.banner('CRITICAL', 'BEHEMOTH ENRAGED');
    if (p === 'dying') {
      hud.toast('BEHEMOTH CRITICAL FAILURE', 3, 'danger');
      this.attacks.reset();
    }
  }

  hit(info: HitInfo) {
    if (!this.alive) return;
    if (this.shield.active) {
      this.shield.hit(info);
      return;
    }
    this.applyDamage(info.damage, info);
    this.ctx.score.bossDamage(info.damage, info.point);
    if (this.alive && this.phase === 'exposed' && this.healthFraction < 0.35) this.enterPhase('critical');
  }

  protected onDestroyed() {
    this.enterPhase('dying');
    this.deathBlasts = 0;
  }

  update(dt: number) {
    this.phaseTime += dt;
    this.shield.update(dt);
    this.radius = this.shield.active ? 5.6 : 3.8;
    if (this.phase === 'dying' || this.phase === 'dead') {
      this.updateDeath(dt);
      return;
    }
    if (this.phase === 'intro') {
      _v.copy(this.moveTarget).sub(this.position);
      this.velocity.copy(_v).multiplyScalar(0.9).clampLength(0, 45);
      if (this.phaseTime > 5 || _v.length() < 4) this.enterPhase('shielded');
    } else {
      this.attacks.update(dt);
      this.move(dt);
      this.escorts(dt);
    }
    this.position.addScaledVector(this.velocity, dt);
    this.position.y = clamp(this.position.y, 50, TUNING.city.ceiling - 20);
    const b = TUNING.city.boundary - 60;
    this.position.x = clamp(this.position.x, -b, b);
    this.position.z = clamp(this.position.z, -b, b);
    this.body?.setNextKinematicTranslation(this.position);
    this.animate(dt);
  }

  private move(dt: number) {
    const player = this.ctx.player;
    const critical = this.phase === 'critical';
    this.retarget -= dt;
    if (this.retarget <= 0 || this.position.distanceTo(this.moveTarget) < 8) {
      const a = rand(0, Math.PI * 2);
      const r = rand(70, 140);
      this.moveTarget.set(player.position.x + Math.cos(a) * r, clamp(player.position.y + rand(15, 55), 90, 210),
        player.position.z + Math.sin(a) * r);
      this.retarget = rand(4, 7) * (critical ? 0.6 : 1);
    }
    if (this.attacks.dashing) {
      this.velocity.copy(this.attacks.dashDir).multiplyScalar(95);
      return;
    }
    const maxSpeed = this.attacks.rooted ? 2 : this.phase === 'shielded' ? 22 : critical ? 40 : 30;
    _v.subVectors(this.moveTarget, this.position).multiplyScalar(0.6).clampLength(0, maxSpeed);
    this.velocity.lerp(_v, damp(critical ? 1.8 : 1.1, dt));
  }

  private escorts(dt: number) {
    this.escortTimer -= dt;
    if (this.escortTimer <= 0) {
      this.escortTimer = this.phase === 'shielded' ? 28 : 22;
      const drones = this.ctx.enemies.list.filter((e) => e.kind === 'drone' && e.alive).length;
      if (drones < 3) this.ctx.enemies.spawnEscort(this.position, this.phase === 'critical' ? 2 : 1);
    }
  }

  private animate(dt: number) {
    const player = this.ctx.player;
    _look.subVectors(player.position, this.position);
    _look.y *= 0.3;
    if (this.attacks.dashing) _look.copy(this.attacks.dashDir);
    if (_look.lengthSq() > 1) {
      quatFromForward(_look.normalize(), UP, _q);
      this.facing.slerp(_q, damp(this.attacks.dashing ? 6 : 2.2, dt));
    }
    // lean into motion
    _v.copy(this.velocity).applyQuaternion(_q.copy(this.facing).invert());
    this.root.quaternion.copy(this.facing)
      .multiply(_q.setFromEuler(new THREE.Euler(clamp(_v.z * 0.008, -0.35, 0.35), 0, clamp(-_v.x * 0.01, -0.3, 0.3))));
    this.root.position.copy(this.position);
    this.root.position.y += Math.sin(this.ctx.time * 1.3) * 0.5;
    // arm cannons track the player
    for (const arm of this.arms) {
      arm.parent!.updateWorldMatrix(true, false);
      _v.copy(player.position);
      arm.parent!.worldToLocal(_v).sub(arm.position).normalize();
      _q.setFromUnitVectors(new THREE.Vector3(0, 0, 1), _v);
      const limited = new THREE.Quaternion().slerp(_q, 0.8);
      arm.quaternion.slerp(limited, damp(4, dt));
    }
    const charge = this.attacks.charge;
    const critical = this.phase === 'critical';
    const flicker = critical && Math.random() < 0.2 ? 0.4 : 1;
    for (const m of this.coreMats) m.emissiveIntensity = (10 + charge * 40 + Math.sin(this.ctx.time * 4) * 3) * flicker;
    const thrust = this.attacks.dashing ? 1 : 0.45 + Math.min(0.5, this.velocity.length() / 60);
    for (const f of this.flames) f.set(thrust, this.ctx.time);
    if (critical) this.damageFx(dt);
  }

  private damageFx(dt: number) {
    this.fxTimer -= dt;
    if (this.fxTimer > 0) return;
    this.fxTimer = 0.07;
    _v.set(rand(-2.5, 2.5), rand(-2, 2.5), rand(-1.5, 1.5)).applyQuaternion(this.root.quaternion).add(this.position);
    this.ctx.fx.explosions.sparkBurst(_v, null, 6, 18, SPARK);
    this.ctx.fx.smoke.emit({ pos: _v, vel: new THREE.Vector3(0, 4, 0), life: 2.5, size: 1.5, size1: 7,
      color: new THREE.Color(0.06, 0.06, 0.06), alpha: 0.75, alpha1: 0, gravity: -1.5 });
    if (Math.random() < 0.04) this.ctx.fx.explosions.spawn(_v, { scale: 0.8, smoke: 2, light: false });
  }

  private updateDeath(dt: number) {
    if (this.phase === 'dead') {
      if (this.phaseTime > 2.5) this.removed = true;
      return;
    }
    // sinking, tilting, chain explosions
    this.velocity.multiplyScalar(Math.exp(-1.2 * dt));
    this.velocity.y -= 4 * dt;
    this.position.addScaledVector(this.velocity, dt);
    this.root.position.copy(this.position);
    this.root.rotateZ(dt * 0.35);
    this.root.rotateX(dt * 0.2);
    for (const f of this.flames) f.set(Math.random() * 0.6, this.ctx.time);
    const due = Math.floor(this.phaseTime / 0.32);
    while (this.deathBlasts < due && this.deathBlasts < 10) {
      this.deathBlasts++;
      _v.set(rand(-3, 3), rand(-3, 3), rand(-3, 3)).add(this.position);
      this.ctx.fx.explosions.spawn(_v, { scale: 1.2 + this.deathBlasts * 0.12, shockwave: this.deathBlasts % 3 === 0 });
      this.ctx.cam.shake(0.35);
      this.ctx.audio.explosion(_v, 1.2);
    }
    this.damageFx(dt);
    if (this.phaseTime > 3.4) {
      this.phase = 'dead';
      this.phaseTime = 0;
      this.ctx.combat.explosion(this.position, { radius: 30, damage: 0, scale: 7, source: 'explosion', shockwave: true });
      this.ctx.fx.rings.emit({ pos: this.position, life: 1.1, size: 12, size1: 160, color: new THREE.Color(3, 1.6, 0.8), alpha: 1, alpha1: 0 });
      this.ctx.cam.shake(1);
      this.root.visible = false;
      if (this.body) {
        this.ctx.physics.removeBody(this.body);
        this.body = null;
      }
      this.ctx.score.kill(SCORE.bossKill, this.position, 'BEHEMOTH DESTROYED');
      this.onDefeated?.();
    }
  }
}
