import * as THREE from 'three';
import { Assets } from '../game/Assets';
import type { GameContext } from '../game/Context';
import { SCORE } from '../game/constants';
import { clamp, damp, interceptTime, quatFromForward, rand, randSign, UP } from '../game/math';
import { G, RAPIER, type HitInfo } from '../physics/Physics';
import { Enemy } from './Enemy';

export type DroneState = 'spawn' | 'approach' | 'orbit' | 'attack' | 'evade' | 'reposition' | 'destroyed';

const BOLT_SPEED = 115;
const MUZZLE = new THREE.Color(3, 0.7, 0.3);
const _v = new THREE.Vector3();
const _to = new THREE.Vector3();
const _desired = new THREE.Vector3();
const _look = new THREE.Vector3();
const _q = new THREE.Quaternion();

/**
 * Aerial combat drone. Finite state machine: Spawn -> Approach -> Orbit <-> Attack / Evade /
 * Reposition -> Destroyed. Each drone rolls its own orbit radius, direction, altitude band and
 * fire cadence so a group never moves in lockstep.
 */
export class Drone extends Enemy {
  readonly kind = 'drone' as const;
  readonly label = 'DRONE';
  state: DroneState = 'spawn';
  private stateTime = 0;
  private readonly orbitRadius = rand(42, 88);
  private readonly orbitSpeed = rand(0.28, 0.6) * randSign();
  private altitude = rand(-6, 26);
  private readonly fireInterval: number;
  private readonly accuracy = rand(0.75, 1.25);
  private orbitAngle = rand(0, Math.PI * 2);
  private fireTimer = rand(1.5, 3.5);
  private burstLeft = 0;
  private burstTimer = 0;
  private muzzleIndex = 0;
  private readonly evadeDir = new THREE.Vector3();
  private readonly phase = rand(0, 10);
  private readonly rotors: THREE.Object3D[] = [];
  private readonly muzzles: THREE.Object3D[];
  private readonly sensorMats: THREE.MeshStandardMaterial[] = [];
  private readonly entry = new THREE.Vector3();
  private readonly look = new THREE.Quaternion();

  constructor(ctx: GameContext, spawn: THREE.Vector3, aggression = 1) {
    super(ctx, 60);
    this.radius = 1.4;
    this.lockTime = 0.95;
    this.fireInterval = rand(1.7, 2.9) / aggression;
    const model = ctx.assets.clone('drone');
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
    for (let i = 0; i < 4; i++) this.rotors.push(Assets.node(model, `Rotor_${i}`));
    this.muzzles = [Assets.node(model, 'Muzzle_L'), Assets.node(model, 'Muzzle_R')];
    model.scale.setScalar(1.25);
    this.root.add(model);
    this.position.copy(spawn);
    this.entry.copy(spawn);
    this.root.position.copy(spawn);
    const k = ctx.physics.kinematic(RAPIER.ColliderDesc.ball(1.5), spawn, G.ENEMY, G.PLAYER | G.DEBRIS);
    this.registerBody(k.body, [k.collider]);
  }

  private setState(s: DroneState) {
    this.state = s;
    this.stateTime = 0;
  }

  update(dt: number) {
    if (!this.alive) return;
    this.stateTime += dt;
    const player = this.ctx.player;
    _to.subVectors(player.position, this.position);
    const dist = _to.length();
    const t = this.ctx.time;
    _desired.set(0, 0, 0);
    switch (this.state) {
      case 'spawn':
        _desired.copy(_to).normalize().multiplyScalar(46);
        if (this.stateTime > 2.2 || dist < this.orbitRadius + 60) this.setState('approach');
        break;
      case 'approach':
        _desired.copy(this.orbitPoint(t)).sub(this.position).normalize().multiplyScalar(40);
        if (dist < this.orbitRadius + 25) this.setState('orbit');
        break;
      case 'orbit': {
        this.orbitAngle += (this.orbitSpeed * dt * 60) / Math.max(this.orbitRadius, 30);
        _desired.copy(this.orbitPoint(t)).sub(this.position).multiplyScalar(1.3);
        if (_desired.length() > 36) _desired.setLength(36);
        this.fireTimer -= dt;
        if (this.fireTimer <= 0 && dist < 240 && player.alive) {
          if (this.ctx.physics.lineOfSight(this.position, player.position)) {
            this.setState('attack');
            this.burstLeft = 3;
            this.burstTimer = 0.35;
          } else this.fireTimer = 0.6;
        }
        if (dist < 20) this.setState('reposition');
        else if (dist < 260 && Math.random() < dt * 0.45 && this.ctx.targeting.angleTo(this.position) < 0.07) this.startEvade();
        break;
      }
      case 'attack':
        _desired.copy(this.orbitPoint(t)).sub(this.position).multiplyScalar(0.4);
        this.burstTimer -= dt;
        if (this.burstLeft > 0 && this.burstTimer <= 0) {
          this.fire(dist);
          this.burstLeft--;
          this.burstTimer = 0.13;
        }
        if (this.burstLeft === 0 && this.stateTime > 0.8) {
          this.fireTimer = this.fireInterval;
          this.setState('orbit');
        }
        break;
      case 'evade':
        _desired.copy(this.evadeDir).multiplyScalar(44);
        if (this.stateTime > 0.6) this.setState('orbit');
        break;
      case 'reposition':
        _desired.copy(_to).normalize().multiplyScalar(-38).add(_v.set(0, 12, 0));
        if (this.stateTime > 1.4) {
          this.altitude = rand(0, 30);
          this.setState('orbit');
        }
        break;
      default:
        break;
    }
    this.steer(dt);
    this.animate(dt, dist);
  }

  private orbitPoint(t: number) {
    const p = this.ctx.player.position;
    return _look.set(
      p.x + Math.cos(this.orbitAngle) * this.orbitRadius,
      Math.max(12, p.y + this.altitude + Math.sin(t * 0.7 + this.phase) * 5),
      p.z + Math.sin(this.orbitAngle) * this.orbitRadius,
    );
  }

  private startEvade() {
    _v.subVectors(this.position, this.ctx.player.position).normalize();
    this.evadeDir.crossVectors(_v, UP).normalize().multiplyScalar(randSign());
    this.evadeDir.y = rand(-0.3, 0.5);
    this.evadeDir.normalize();
    this.setState('evade');
  }

  private steer(dt: number) {
    // obstacle avoidance: feel ahead along the velocity
    const speed = this.velocity.length();
    if (speed > 2) {
      _v.copy(this.velocity).divideScalar(speed);
      const hit = this.ctx.physics.raycast(this.position, _v, 8 + speed * 0.6, G.WORLD);
      if (hit) _desired.addScaledVector(hit.normal, 40).add(_v.set(0, 18, 0));
    }
    // separation from other drones
    for (const e of this.ctx.enemies.list) {
      if (e === this || e.kind !== 'drone' || !e.alive) continue;
      const d = this.position.distanceTo(e.position);
      if (d < 10 && d > 0.01) _desired.addScaledVector(_v.subVectors(this.position, e.position).normalize(), (10 - d) * 4);
    }
    if (this.position.y < 10) _desired.y += (10 - this.position.y) * 4;
    _v.subVectors(_desired, this.velocity);
    const maxDv = 34 * dt;
    if (_v.length() > maxDv) _v.setLength(maxDv);
    this.velocity.add(_v);
    this.position.addScaledVector(this.velocity, dt);
    this.body!.setNextKinematicTranslation(this.position);
  }

  private animate(dt: number, dist: number) {
    // face the player while engaging, otherwise the direction of travel; bank into turns
    const engaging = this.state === 'orbit' || this.state === 'attack';
    if (engaging && dist > 1) _look.subVectors(this.ctx.player.position, this.position).normalize();
    else if (this.velocity.lengthSq() > 1) _look.copy(this.velocity).normalize();
    else _look.set(0, 0, 1);
    quatFromForward(_look, UP, _q);
    this.look.slerp(_q, damp(6, dt));
    this.root.quaternion.copy(this.look);
    const lateral = clamp(this.velocity.dot(_v.set(1, 0, 0).applyQuaternion(this.look)) * 0.02, -0.5, 0.5);
    this.root.rotateZ(-lateral);
    this.root.position.copy(this.position);
    for (let i = 0; i < 4; i++) this.rotors[i].rotation.y += dt * (i % 2 ? 42 : -42);
    this.hitFlash = Math.max(0, this.hitFlash - dt * 4);
    const pulse = 10 + Math.sin(this.ctx.time * 8 + this.phase) * 3 + this.hitFlash * 30 + (this.state === 'attack' ? 12 : 0);
    for (const m of this.sensorMats) m.emissiveIntensity = pulse;
  }

  private fire(dist: number) {
    const player = this.ctx.player;
    const muzzle = this.muzzles[this.muzzleIndex++ % 2].getWorldPosition(new THREE.Vector3());
    const tti = interceptTime(muzzle, player.position, player.flight.vel, BOLT_SPEED);
    const aim = _v.copy(player.position).addScaledVector(player.flight.vel, tti * 0.9);
    const spread = (1.5 + dist * 0.018 + player.speed * 0.03) * this.accuracy;
    aim.x += rand(-spread, spread);
    aim.y += rand(-spread, spread) * 0.7;
    aim.z += rand(-spread, spread);
    const dir = aim.sub(muzzle).normalize();
    this.ctx.bolts.fire(muzzle, dir.multiplyScalar(BOLT_SPEED), 6);
    this.ctx.fx.muzzle(muzzle, 0.8, MUZZLE);
    this.ctx.audio.enemyShot(muzzle);
  }

  protected onDamaged(_info: HitInfo) {
    if (this.alive && this.state !== 'evade' && Math.random() < 0.45) this.startEvade();
  }

  protected onDestroyed() {
    this.state = 'destroyed';
    this.ctx.combat.explosion(this.position, { radius: 7, damage: 25, scale: 1.4, source: 'explosion', shockwave: false });
    this.ctx.score.kill(SCORE.drone, this.position, 'DRONE DOWN');
    this.removed = true;
  }
}
