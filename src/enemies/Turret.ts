import * as THREE from 'three';
import { Assets } from '../game/Assets';
import type { GameContext } from '../game/Context';
import { SCORE } from '../game/constants';
import { clamp, interceptTime, smoothstep } from '../game/math';
import { G, RAPIER } from '../physics/Physics';
import { Enemy } from './Enemy';

export type TurretState = 'idle' | 'acquire' | 'track' | 'fire' | 'cooldown' | 'destroyed';

const RANGE = 380;
const MISSILE_SPEED_EST = 62;
const YAW_RATE = 1.5;
const PITCH_RATE = 1.1;
const _v = new THREE.Vector3();
const _aim = new THREE.Vector3();
const _pivot = new THREE.Vector3();
const _dir = new THREE.Vector3();

function wrap(a: number) {
  while (a > Math.PI) a -= Math.PI * 2;
  while (a < -Math.PI) a += Math.PI * 2;
  return a;
}

/**
 * Rooftop missile battery. Idle scan -> Acquire (warning) -> Track with a lead solution ->
 * Fire a missile pair -> Cooldown. The yaw ring and pitch head rotate at finite rates and the
 * missiles leave along the head's actual facing.
 */
export class Turret extends Enemy {
  readonly kind = 'turret' as const;
  readonly label = 'TURRET';
  state: TurretState = 'idle';
  private stateTime = 0;
  private yaw = 0;
  private pitch = 0;
  private readonly yawNode: THREE.Object3D;
  private readonly pitchNode: THREE.Object3D;
  private readonly muzzles: THREE.Object3D[];
  private readonly sensorMats: THREE.MeshStandardMaterial[] = [];
  private shots = 0;
  private shotTimer = 0;
  private muzzleIndex = 0;
  private rise = 0;
  private readonly base = new THREE.Vector3();
  private smokeTimer = 0;

  constructor(ctx: GameContext, anchor: THREE.Vector3, facing: number) {
    super(ctx, 220);
    this.radius = 2.2;
    this.lockTime = 1.1;
    const model = ctx.assets.clone('turret');
    model.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) {
        m.castShadow = true;
        if ((m.material as THREE.Material).name === 'Emissive_Red') {
          m.material = (m.material as THREE.MeshStandardMaterial).clone();
          this.sensorMats.push(m.material as THREE.MeshStandardMaterial);
        }
      }
    });
    this.yawNode = Assets.node(model, 'Yaw');
    this.pitchNode = Assets.node(model, 'Pitch');
    this.muzzles = [0, 1, 2, 3].map((i) => Assets.node(model, `Muzzle_${i}`));
    model.scale.setScalar(1.3);
    this.root.add(model);
    this.base.copy(anchor);
    this.yaw = facing;
    this.root.position.copy(anchor).setY(anchor.y - 3.5);
    this.position.copy(anchor).setY(anchor.y + 2.2);
    const k = ctx.physics.kinematic(
      RAPIER.ColliderDesc.cuboid(1.9, 1.9, 1.9).setTranslation(0, 1.9, 0),
      this.base,
      G.ENEMY,
      G.PLAYER | G.DEBRIS,
    );
    this.registerBody(k.body, [k.collider]);
    ctx.audio.turretRise(anchor);
  }

  private setState(s: TurretState) {
    this.state = s;
    this.stateTime = 0;
  }

  update(dt: number) {
    this.stateTime += dt;
    if (!this.alive) {
      // wrecked: keep smoking
      this.smokeTimer -= dt;
      if (this.smokeTimer <= 0) {
        this.smokeTimer = 0.12;
        this.ctx.fx.smoke.emit({ pos: this.position, vel: _v.set(0, 3, 0), life: 3, size: 1.5, size1: 6,
          color: new THREE.Color(0.08, 0.08, 0.08), alpha: 0.7, alpha1: 0, gravity: -1 });
      }
      if (this.stateTime > 20) this.removed = true;
      return;
    }
    // rise out of the roof when deployed
    this.rise = Math.min(1, this.rise + dt / 1.4);
    this.root.position.y = this.base.y - 3.5 * (1 - smoothstep(0, 1, this.rise));
    const player = this.ctx.player;
    const dist = this.position.distanceTo(player.position);
    const visible = dist < RANGE && player.alive && this.rise >= 1 && this.canSee();
    // lead solution for the missile's average speed
    this.pitchNode.getWorldPosition(_pivot);
    const t = interceptTime(_pivot, player.position, player.flight.vel, MISSILE_SPEED_EST);
    _aim.copy(player.position).addScaledVector(player.flight.vel, clamp(t, 0, 4));
    _dir.subVectors(_aim, _pivot);
    const wantYaw = Math.atan2(_dir.x, _dir.z);
    const wantPitch = clamp(Math.atan2(_dir.y, Math.hypot(_dir.x, _dir.z)) + 0.05, -0.35, 1.2);
    let track = false;
    switch (this.state) {
      case 'idle':
        this.yaw += dt * 0.35 * Math.sin(this.ctx.time * 0.3 + this.id);
        this.pitch += (0.1 - this.pitch) * dt;
        if (visible) {
          this.setState('acquire');
          this.ctx.audio.turretWarn(this.position);
        }
        break;
      case 'acquire':
        track = true;
        if (!visible) this.setState('idle');
        else if (this.stateTime > 0.9) this.setState('track');
        break;
      case 'track':
        track = true;
        if (!visible && this.stateTime > 2) this.setState('idle');
        else if (this.stateTime > 1.1 && Math.abs(wrap(wantYaw - this.yaw)) < 0.07 && Math.abs(wantPitch - this.pitch) < 0.08) {
          this.setState('fire');
          this.shots = 2;
          this.shotTimer = 0;
        }
        break;
      case 'fire':
        track = true;
        this.shotTimer -= dt;
        if (this.shots > 0 && this.shotTimer <= 0) {
          this.launch();
          this.shots--;
          this.shotTimer = 0.35;
        }
        if (this.shots === 0 && this.stateTime > 0.5) this.setState('cooldown');
        break;
      case 'cooldown':
        track = true;
        if (this.stateTime > 3.6) this.setState(visible ? 'track' : 'idle');
        break;
      default:
        break;
    }
    if (track) {
      this.yaw += clamp(wrap(wantYaw - this.yaw), -YAW_RATE * dt, YAW_RATE * dt);
      this.pitch += clamp(wantPitch - this.pitch, -PITCH_RATE * dt, PITCH_RATE * dt);
    }
    this.yaw = wrap(this.yaw);
    this.yawNode.rotation.set(0, this.yaw, 0);
    this.pitchNode.rotation.set(-this.pitch, 0, 0);
    this.hitFlash = Math.max(0, this.hitFlash - dt * 4);
    const alert = this.state === 'idle' ? 6 : this.state === 'acquire' ? 12 + Math.sin(this.ctx.time * 30) * 10 : 18;
    for (const m of this.sensorMats) m.emissiveIntensity = alert + this.hitFlash * 30;
  }

  private canSee() {
    return this.ctx.physics.lineOfSight(_v.copy(this.position).setY(this.position.y + 1.5), this.ctx.player.position);
  }

  private launch() {
    const muzzle = this.muzzles[this.muzzleIndex++ % 4];
    const pos = muzzle.getWorldPosition(new THREE.Vector3());
    const dir = new THREE.Vector3(0, 0, 1).applyQuaternion(this.pitchNode.getWorldQuaternion(new THREE.Quaternion()));
    this.ctx.missiles.fireHostile(pos, dir, 38);
    this.ctx.fx.muzzle(pos, 2.2, new THREE.Color(3, 1.2, 0.5));
    this.ctx.fx.smoke.emit({ pos, vel: dir.clone().multiplyScalar(-6), life: 1.6, size: 1.5, size1: 5,
      color: new THREE.Color(0.6, 0.58, 0.56), alpha: 0.7, alpha1: 0, drag: 2 });
  }

  protected onDestroyed() {
    this.state = 'destroyed';
    this.stateTime = 0;
    this.ctx.combat.explosion(this.position, { radius: 9, damage: 40, scale: 2, source: 'explosion', shockwave: true });
    this.ctx.score.kill(SCORE.turret, this.position, 'TURRET DESTROYED');
    this.pitchNode.visible = false;
    this.yawNode.rotation.z = 0.4;
    if (this.body) {
      this.ctx.physics.removeBody(this.body);
      this.body = null;
    }
  }

  get lockable() {
    return this.alive && this.rise >= 1;
  }
}
