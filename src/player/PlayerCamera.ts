import * as THREE from 'three';
import type { GameContext } from '../game/Context';
import { TUNING } from '../game/constants';
import { clamp, damp, wobble } from '../game/math';
import { G, type RayHit } from '../physics/Physics';

const FLIP = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.PI);
const AIM_MASK = G.WORLD | G.ENEMY | G.SHIELD | G.ENEMY_MISSILE | G.DEBRIS;
const _off = new THREE.Vector3();
const _v = new THREE.Vector3();
const _dir = new THREE.Vector3();
const _q = new THREE.Quaternion();
const _e = new THREE.Euler();

/**
 * Third-person chase camera: damped orientation, acceleration lag, speed-dependent distance and
 * FOV, collision pull-in, trauma shake and weapon recoil. Also resolves the aim point under the
 * crosshair used by every weapon.
 */
export class PlayerCamera {
  readonly aimPoint = new THREE.Vector3();
  readonly aimDir = new THREE.Vector3();
  aimHit: RayHit | null = null;
  private readonly q = new THREE.Quaternion();
  private readonly pos = new THREE.Vector3();
  private readonly smoothVel = new THREE.Vector3();
  private trauma = 0;
  private recoil = 0;
  private snapNext = true;
  private t = 0;

  constructor(private readonly ctx: GameContext, private readonly camera: THREE.PerspectiveCamera) {}

  shake(amount: number) {
    this.trauma = Math.min(1, this.trauma + amount);
  }

  kick(amount: number) {
    this.recoil = Math.min(1.5, this.recoil + amount);
  }

  snap() {
    this.snapNext = true;
  }

  update(dt: number) {
    const player = this.ctx.player;
    const flight = player.flight;
    this.t += dt;
    const speed = player.speed;
    const speedF = clamp(speed / TUNING.flight.boostSpeed, 0, 1);
    if (this.snapNext) {
      this.q.copy(flight.q);
      this.smoothVel.copy(flight.vel);
    } else if (player.alive) {
      this.q.slerp(flight.q, damp(player.flightBlend > 0.5 ? 8 : 12, dt));
    }
    // desired offset behind and above, pulled back with speed; higher in flight so the suit's
    // back reads instead of being seen end-on
    const stand = player.standBlend;
    const fb = player.flightBlend;
    _off.set(0, 1.5 + fb * 0.9 + 0.3 * speedF - stand * 0.2, -(5.8 + fb * 0.8 + 2.8 * speedF - stand * 1.0)).applyQuaternion(this.q);
    const head = _v.copy(player.position).setY(player.position.y + 0.7);
    const desired = new THREE.Vector3().addVectors(head, _off);
    // lag behind acceleration
    this.smoothVel.lerp(flight.vel, damp(3.2, dt));
    const lag = _dir.subVectors(flight.vel, this.smoothVel).multiplyScalar(0.07);
    if (lag.length() > 3.2) lag.setLength(3.2);
    desired.sub(lag);
    // keep the camera out of walls
    _dir.subVectors(desired, head);
    const dist = _dir.length();
    _dir.divideScalar(dist);
    const block = this.ctx.physics.raycast(head, _dir, dist + 0.6, G.WORLD);
    if (block) desired.copy(head).addScaledVector(_dir, Math.max(1.0, block.distance - 0.6));
    if (this.snapNext) this.pos.copy(desired);
    else this.pos.lerp(desired, damp(30, dt));
    this.snapNext = false;

    // shake: trauma^2 scaled noise plus a constant buzz while boosting
    this.trauma = Math.max(0, this.trauma - dt * 1.3);
    let s = this.trauma * this.trauma;
    if (flight.boosting) s += 0.025;
    this.recoil *= Math.exp(-11 * dt);
    const k = this.t * 22;
    this.camera.position.copy(this.pos);
    this.camera.position.x += wobble(k, 1) * s * 0.6;
    this.camera.position.y += wobble(k, 2) * s * 0.6;
    this.camera.position.z += wobble(k, 3) * s * 0.6;
    this.camera.quaternion.copy(this.q).multiply(FLIP);
    // look slightly down while flying so the suit sits in the lower third under the reticle
    _e.set(-fb * 0.1 + wobble(k, 4) * s * 0.05 + this.recoil * 0.018, wobble(k, 5) * s * 0.05, wobble(k, 6) * s * 0.07);
    this.camera.quaternion.multiply(_q.setFromEuler(_e));
    this.camera.getWorldDirection(this.aimDir);
    this.camera.position.addScaledVector(this.aimDir, -this.recoil * 0.3);

    const fov = 70 + speedF * 10 + (flight.boosting ? 8 : 0);
    this.camera.fov += (fov - this.camera.fov) * damp(4, dt);
    this.camera.updateProjectionMatrix();

    // aim point under the crosshair (ignore hits between the camera and the suit)
    this.camera.updateMatrixWorld();
    const hit = this.ctx.physics.raycast(this.camera.position, this.aimDir, 1600, AIM_MASK);
    const minDist = this.camera.position.distanceTo(player.position) + 1.5;
    if (hit && hit.distance > minDist) {
      this.aimHit = hit;
      this.aimPoint.copy(hit.point);
    } else {
      this.aimHit = null;
      this.aimPoint.copy(this.camera.position).addScaledVector(this.aimDir, 1200);
    }
  }
}
