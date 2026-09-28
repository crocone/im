import * as THREE from 'three';
import { TUNING } from '../game/constants';
import { clamp, damp, FORWARD, RIGHT, rotateToward, UP } from '../game/math';

export type FlightMode = 'hover' | 'flight';

export interface FlightInput {
  forward: number;
  strafe: number;
  vertical: number;
  roll: number;
  /** yaw / pitch deltas in radians for this frame (mouse) */
  yaw: number;
  pitch: number;
  boost: boolean;
}

const F = TUNING.flight;
const H = TUNING.hover;
const _f = new THREE.Vector3();
const _r = new THREE.Vector3();
const _u = new THREE.Vector3();
const _a = new THREE.Vector3();
const _q = new THREE.Quaternion();
const _level = new THREE.Vector3();
const _tmp = new THREE.Vector3();
const _prev = new THREE.Vector3();

/**
 * Powered flight dynamics. Orientation is a full quaternion (6DoF) with roll assist; motion is
 * acceleration + drag driven so the suit has inertia. The resulting velocity is handed to a
 * Rapier rigid body which resolves collisions and feeds the corrected velocity back.
 */
export class FlightModel {
  readonly q = new THREE.Quaternion();
  readonly vel = new THREE.Vector3();
  /** smoothed acceleration in world space (visual lean, camera lag) */
  readonly accel = new THREE.Vector3();
  mode: FlightMode = 'hover';
  boosting = false;
  /** 0..1 overall thruster output */
  thrust = 0;
  /** smoothed yaw rate (rad/s) for banking */
  yawRate = 0;
  private stallTimer = 0;

  forward(out = new THREE.Vector3()) {
    return out.copy(FORWARD).applyQuaternion(this.q);
  }

  right(out = new THREE.Vector3()) {
    return out.copy(RIGHT).applyQuaternion(this.q);
  }

  up(out = new THREE.Vector3()) {
    return out.copy(UP).applyQuaternion(this.q);
  }

  setMode(mode: FlightMode) {
    this.mode = mode;
    this.stallTimer = 0;
  }

  update(dt: number, input: FlightInput, canBoost: boolean) {
    this.rotate(dt, input);
    this.boosting = input.boost && canBoost;
    if (this.boosting && this.mode === 'hover') this.mode = 'flight';
    _prev.copy(this.vel);
    if (this.mode === 'hover') this.hover(dt, input);
    else this.fly(dt, input);
    // smoothed acceleration for secondary motion
    _tmp.subVectors(this.vel, _prev).divideScalar(Math.max(dt, 1e-4));
    this.accel.lerp(_tmp, damp(8, dt));
    this.yawRate += (input.yaw / Math.max(dt, 1e-4) - this.yawRate) * damp(10, dt);
  }

  private rotate(dt: number, input: FlightInput) {
    if (this.mode === 'hover') {
      // yaw around the world vertical keeps the horizon steady while hovering
      _q.setFromAxisAngle(UP, input.yaw);
      this.q.premultiply(_q);
    } else {
      _q.setFromAxisAngle(UP, input.yaw);
      this.q.multiply(_q);
      _q.setFromAxisAngle(FORWARD, input.roll * F.rollRate * dt);
      this.q.multiply(_q);
    }
    _q.setFromAxisAngle(_tmp.set(1, 0, 0), input.pitch);
    this.q.multiply(_q);
    this.q.normalize();

    // roll assist: bring the wings level unless the pilot is actively rolling
    this.forward(_f);
    this.right(_r);
    const assist = this.mode === 'hover' ? 10 : Math.abs(input.roll) > 0.1 ? 0 : F.rollAssist;
    if (Math.abs(_f.y) < 0.96 && assist > 0) {
      _level.crossVectors(_f, UP).normalize();
      const angle = Math.atan2(_f.dot(_tmp.crossVectors(_level, _r)), _level.dot(_r));
      _q.setFromAxisAngle(_f, -angle * Math.min(1, assist * dt));
      this.q.premultiply(_q).normalize();
    }
    if (this.mode === 'hover') {
      const pitch = Math.asin(clamp(this.forward(_f).y, -1, 1));
      const excess = Math.abs(pitch) - H.pitchLimit;
      if (excess > 0) {
        _q.setFromAxisAngle(_tmp.set(1, 0, 0), Math.sign(pitch) * excess);
        this.q.multiply(_q).normalize();
      }
    }
  }

  private hover(dt: number, input: FlightInput) {
    this.forward(_f);
    _f.y = 0;
    if (_f.lengthSq() < 1e-4) this.up(_f).negate().setY(0);
    _f.normalize();
    _r.crossVectors(_f, UP).normalize();
    _a.set(0, 0, 0)
      .addScaledVector(_f, input.forward * H.accel)
      .addScaledVector(_r, input.strafe * H.accel)
      .addScaledVector(UP, input.vertical * H.verticalAccel);
    this.vel.addScaledVector(_a, dt);
    // stabilisers: gentle damping while pushing, strong hold when released
    const moving = Math.abs(input.forward) + Math.abs(input.strafe) > 0.1;
    const hDamp = moving ? H.accel / H.maxSpeed : H.damping;
    const vDamp = Math.abs(input.vertical) > 0.1 ? H.verticalAccel / (H.maxSpeed * 0.8) : H.damping;
    const kh = Math.exp(-hDamp * dt);
    this.vel.x *= kh;
    this.vel.z *= kh;
    this.vel.y *= Math.exp(-vDamp * dt);
    const speed = this.vel.length();
    if (speed > H.maxSpeed * 1.6) this.vel.multiplyScalar(1 - Math.min(1, 2 * dt));
    const push = Math.min(1, _a.length() / H.accel);
    this.thrust += (0.35 + 0.65 * push - this.thrust) * damp(6, dt);
  }

  private fly(dt: number, input: FlightInput) {
    this.forward(_f);
    this.right(_r);
    this.up(_u);
    const fwd = this.boosting ? 1 : input.forward;
    const accel = this.boosting ? F.boostAccel : F.accel;
    _a.set(0, 0, 0)
      .addScaledVector(_f, fwd * accel)
      .addScaledVector(_r, input.strafe * F.strafeAccel)
      .addScaledVector(_u, input.vertical * F.verticalAccel);
    this.vel.addScaledVector(_a, dt);
    const vmax = this.boosting ? F.boostSpeed : F.maxSpeed;
    const k = accel / (vmax * vmax);
    let speed = this.vel.length();
    this.vel.multiplyScalar(1 / (1 + k * speed * dt));
    this.vel.multiplyScalar(Math.exp(-F.linearDrag * dt));
    speed = this.vel.length();
    // aerodynamic grip: the velocity vector is gradually carried round with the suit's heading
    if (speed > 4) {
      _tmp.copy(this.vel).divideScalar(speed);
      const grip = F.velocityAlign * clamp(speed / 40, 0.2, 1) * (fwd > 0.1 ? 1 : 0.4);
      rotateToward(_tmp, _f, grip * dt);
      this.vel.copy(_tmp).multiplyScalar(speed);
    }
    const push = Math.min(1, _a.length() / F.accel);
    const target = this.boosting ? 1 : 0.3 + 0.55 * push;
    this.thrust += (target - this.thrust) * damp(5, dt);
    // stall into hover when slow with no thrust input
    const idle = Math.abs(input.forward) + Math.abs(input.strafe) + Math.abs(input.vertical) < 0.1;
    this.stallTimer = speed < 6 && idle && !this.boosting ? this.stallTimer + dt : 0;
    if (this.stallTimer > 1.2) this.setMode('hover');
  }
}
