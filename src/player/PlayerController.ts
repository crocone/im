import * as THREE from 'three';
import type { GameContext } from '../game/Context';
import { TUNING } from '../game/constants';
import { damp, rand, smoothstep, UP } from '../game/math';
import { G, groups, RAPIER, type HitInfo, type Hittable } from '../physics/Physics';
import { FlightModel, type FlightInput } from './FlightModel';
import { PlayerVisual } from './PlayerVisual';

const _v = new THREE.Vector3();
const _q = new THREE.Quaternion();
const _axis = new THREE.Vector3();
const DOWN = new THREE.Vector3(0, -1, 0);
const SPARK = new THREE.Color(3, 2, 1);

/** The powered armor: input -> flight model -> Rapier body, plus armor / energy / ammo state. */
export class PlayerController implements Hittable {
  readonly kind = 'player' as const;
  readonly flight = new FlightModel();
  readonly visual: PlayerVisual;
  readonly body: RAPIER.RigidBody;
  readonly collider: RAPIER.Collider;
  readonly position = new THREE.Vector3();
  armor: number = TUNING.armor.max;
  energy: number = TUNING.energy.max;
  missiles: number = TUNING.missiles.max;
  minis: number = TUNING.missiles.miniMax;
  alive = true;
  grounded = false;
  flightBlend = 0;
  standBlend = 1;
  strafeInput = 0;
  outOfBounds = false;
  onDestroyed: (() => void) | null = null;
  private energyIdle = 0;
  private sinceHit = 99;
  private exhausted = false;
  private regenTimer = 0;
  private deathTimer = 0;
  private exploded = false;
  private notified = false;
  private readonly preVel = new THREE.Vector3();

  constructor(private readonly ctx: GameContext) {
    this.visual = new PlayerVisual(ctx.scene, ctx.assets, ctx.fx.textures);
    this.body = ctx.physics.world.createRigidBody(
      RAPIER.RigidBodyDesc.dynamic().lockRotations().setGravityScale(0).setCcdEnabled(true).setLinearDamping(0),
    );
    this.collider = ctx.physics.world.createCollider(
      RAPIER.ColliderDesc.capsule(0.55, 0.42)
        .setDensity(90)
        .setFriction(0.3)
        .setCollisionGroups(groups(G.PLAYER, G.WORLD | G.ENEMY | G.SHIELD | G.DEBRIS | G.BOUNDARY)),
      this.body,
    );
    ctx.physics.register(this.collider, this);
  }

  reset(spawn: THREE.Vector3, yaw: number) {
    this.armor = TUNING.armor.max;
    this.energy = TUNING.energy.max;
    this.missiles = TUNING.missiles.max;
    this.minis = TUNING.missiles.miniMax;
    this.alive = true;
    this.exploded = false;
    this.notified = false;
    this.sinceHit = 99;
    this.deathTimer = 0;
    this.exhausted = false;
    this.flight.vel.set(0, 0, 0);
    this.flight.q.setFromAxisAngle(UP, yaw);
    this.flight.setMode('hover');
    this.position.copy(spawn);
    this.body.setTranslation(spawn, true);
    this.body.setLinvel({ x: 0, y: 0, z: 0 }, true);
    this.body.setGravityScale(0, true);
    this.standBlend = 1;
    this.flightBlend = 0;
    this.visual.setVisible(true);
  }

  get speed() {
    return this.flight.vel.length();
  }

  /** MissileTarget interface (hostile missiles home on the suit). */
  get velocity() {
    return this.flight.vel;
  }

  readonly radius = 1;

  /** Spend energy for a repulsor shot / boost; false if the capacitor is too low. */
  spend(cost: number): boolean {
    if (this.energy < cost) return false;
    this.energy -= cost;
    this.energyIdle = 0;
    return true;
  }

  repair(amount: number) {
    this.armor = Math.min(TUNING.armor.max, this.armor + amount);
  }

  refill() {
    this.energy = TUNING.energy.max;
    this.missiles = TUNING.missiles.max;
    this.minis = TUNING.missiles.miniMax;
  }

  /** Called before the physics step. */
  update(dt: number) {
    const { input } = this.ctx;
    const sens = TUNING.flight.mouseSensitivity;
    const fi: FlightInput = {
      forward: input.axis('KeyS', 'KeyW'),
      strafe: input.axis('KeyA', 'KeyD'),
      vertical: input.axis('KeyC', 'Space'),
      roll: input.axis('KeyQ', 'KeyE'),
      yaw: -input.mouseDX * sens,
      pitch: input.mouseDY * sens * (input.invertY ? -1 : 1),
      boost: input.down('ShiftLeft') || input.down('ShiftRight'),
    };
    if (!this.alive) {
      this.updateDeath(dt);
      return;
    }
    this.strafeInput = fi.strafe;
    if (input.justPressed('KeyF')) {
      this.flight.setMode(this.flight.mode === 'hover' ? 'flight' : 'hover');
      this.ctx.hud.toast(this.flight.mode === 'hover' ? 'HOVER MODE' : 'FLIGHT MODE');
    }
    // capacitor: boost drains, everything else recharges after a short delay
    if (this.energy < 1) this.exhausted = true;
    if (this.exhausted && this.energy > 25) this.exhausted = false;
    const wantsBoost = fi.boost && !this.exhausted;
    this.flight.update(dt, fi, wantsBoost);
    if (this.flight.boosting) {
      this.energy = Math.max(0, this.energy - TUNING.energy.boostDrain * dt);
      this.energyIdle = 0;
    }
    this.energyIdle += dt;
    // suit auto-repair: slowly patches armor back to 50 % after a few seconds out of fire
    this.sinceHit += dt;
    if (this.sinceHit > 5 && this.armor < 50) this.armor = Math.min(50, this.armor + 1.5 * dt);
    if (this.energyIdle > TUNING.energy.regenDelay)
      this.energy = Math.min(TUNING.energy.max, this.energy + TUNING.energy.regen * dt);
    this.regenTimer += dt;
    if (this.regenTimer > TUNING.missiles.regenInterval) {
      this.regenTimer = 0;
      this.missiles = Math.min(TUNING.missiles.max, this.missiles + 1);
      this.minis = Math.min(TUNING.missiles.miniMax, this.minis + 3);
    }
    // take off automatically when pushing off a surface
    if (this.grounded && (Math.abs(fi.forward) + Math.abs(fi.strafe) > 0.1 || fi.vertical > 0))
      this.flight.vel.y = Math.max(this.flight.vel.y, 3);
    if (this.grounded && fi.vertical <= 0 && this.flight.mode === 'hover') this.flight.vel.y = Math.max(this.flight.vel.y, -1);
    // pose blends
    const speed = this.speed;
    const flightTarget = this.flight.mode === 'flight' ? Math.max(smoothstep(2, 16, speed), this.flight.boosting ? 1 : 0) : 0;
    this.flightBlend += (flightTarget - this.flightBlend) * damp(3, dt);
    const standTarget = this.grounded && speed < 1.5 && this.flight.mode === 'hover' ? 1 : 0;
    this.standBlend += (standTarget - this.standBlend) * damp(6, dt);
    this.applyToBody();
  }

  private applyToBody() {
    this.preVel.copy(this.flight.vel);
    this.body.setLinvel(this.flight.vel, true);
    // capsule axis follows the body: upright when hovering, along the heading in flight
    this.flight.forward(_axis);
    _q.setFromUnitVectors(UP, _axis);
    _q.slerpQuaternions(_identity, _q, this.flightBlend);
    this.body.setRotation(_q, true);
  }

  /** Called after the physics step: read back the collision-corrected state. */
  afterPhysics() {
    const t = this.body.translation();
    this.position.set(t.x, t.y, t.z);
    const lv = this.body.linvel();
    if (this.alive) {
      _v.set(lv.x, lv.y, lv.z);
      const dv = _v.distanceTo(this.preVel);
      if (dv > TUNING.armor.collisionThreshold) {
        const dmg = (dv - TUNING.armor.collisionThreshold) * 0.8;
        _v.copy(this.preVel).normalize();
        this.hit({ damage: dmg, point: this.position.clone().addScaledVector(_v, 0.9), dir: _v.clone(), source: 'collision', impulse: 0 });
        this.ctx.audio.thud(Math.min(1, dv / 80));
      }
      this.flight.vel.set(lv.x, lv.y, lv.z);
    }
    const hit = this.ctx.physics.raycast(this.position, DOWN, 1.2, G.WORLD | G.DEBRIS, this.collider);
    this.grounded = hit !== null && this.flightBlend < 0.5 && this.flight.vel.y < 1.5;
    const b = TUNING.city.boundary;
    this.outOfBounds = Math.abs(this.position.x) > b || Math.abs(this.position.z) > b || this.position.y > TUNING.city.ceiling;
  }

  updateVisual(dt: number) {
    this.visual.update(
      dt,
      {
        aim: this.flight.q,
        vel: this.flight.vel,
        accel: this.flight.accel,
        flightBlend: this.flightBlend,
        standBlend: this.standBlend,
        thrust: this.flight.thrust,
        boosting: this.flight.boosting,
        strafe: this.strafeInput,
        yawRate: this.flight.yawRate,
        time: this.ctx.time,
        armor: this.armor,
      },
      this.position,
      this.alive,
    );
  }

  hit(info: HitInfo) {
    if (!this.alive) return;
    this.sinceHit = 0;
    this.armor = Math.max(0, this.armor - info.damage);
    this.ctx.fx.explosions.sparkBurst(info.point, info.dir.clone().negate(), 14, 16, SPARK);
    this.ctx.hud.damage(Math.min(1, info.damage / 25));
    this.ctx.cam.shake(Math.min(0.9, 0.25 + info.damage / 35));
    this.ctx.audio.playerHit();
    if (this.armor <= 0) this.destroy();
  }

  private destroy() {
    this.alive = false;
    this.deathTimer = 0;
    this.body.setGravityScale(1.6, true);
    this.visual.tumble.set(rand(-4, 4), rand(-3, 3), rand(-6, 6));
    this.ctx.hud.toast('ARMOR CRITICAL — SUIT FAILURE', 3);
    this.ctx.audio.alarm();
  }

  private updateDeath(dt: number) {
    this.deathTimer += dt;
    this.flight.thrust = 0;
    this.flight.boosting = false;
    if (!this.exploded) {
      if (Math.random() < 0.6) this.ctx.fx.explosions.sparkBurst(this.position, null, 3, 12);
      this.ctx.fx.trail(this.position, this.position.clone().add(_v.set(0, 0.3, 0)), 0.2, 0.8, 1.6);
      if (this.deathTimer > 2.6 || (this.grounded && this.deathTimer > 0.6)) {
        this.exploded = true;
        this.ctx.combat.explosion(this.position, { radius: 10, damage: 0, scale: 2.2, source: 'enemy', shockwave: true });
        this.visual.setVisible(false);
        this.body.setLinvel({ x: 0, y: 0, z: 0 }, true);
        this.body.setGravityScale(0, true);
      }
    } else if (this.deathTimer > 4.2 && !this.notified) {
      this.notified = true;
      this.onDestroyed?.();
    }
  }
}

const _identity = new THREE.Quaternion();
