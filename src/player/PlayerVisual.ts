import * as THREE from 'three';
import { Assets } from '../game/Assets';
import { clamp, damp, FORWARD, UP } from '../game/math';
import type { FxTextures } from '../fx/textures';
import { ThrusterFlame } from '../fx/ThrusterFlame';

export type Side = 'L' | 'R';

export interface VisualState {
  aim: THREE.Quaternion;
  vel: THREE.Vector3;
  accel: THREE.Vector3;
  flightBlend: number;
  standBlend: number;
  thrust: number;
  boosting: boolean;
  strafe: number;
  yawRate: number;
  time: number;
  armor: number;
}

const HAND_AIM = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), -Math.PI / 2);
const IDENT = new THREE.Quaternion();
const DOWN = new THREE.Vector3(0, -1, 0);
const _q = new THREE.Quaternion();
const _q2 = new THREE.Quaternion();
const _v = new THREE.Vector3();
const _v2 = new THREE.Vector3();
const _f = new THREE.Vector3();
const _e = new THREE.Euler();
const _pq = new THREE.Quaternion();

/** The rendered armor: pose blending (standing / hover / flight), banking, arm aiming, thrusters. */
export class PlayerVisual {
  readonly root: THREE.Object3D;
  private readonly mixer: THREE.AnimationMixer;
  private readonly actions: Record<'standing' | 'hover' | 'flight', THREE.AnimationAction>;
  private readonly arm: Record<Side, THREE.Object3D>;
  private readonly forearm: Record<Side, THREE.Object3D>;
  private readonly hand: Record<Side, THREE.Object3D>;
  readonly palm: Record<Side, THREE.Object3D>;
  readonly launcher: Record<Side, THREE.Object3D>;
  readonly miniLauncher: Record<Side, THREE.Object3D>;
  private readonly palmFlame: Record<Side, ThrusterFlame>;
  private readonly footFlame: Record<Side, ThrusterFlame>;
  private readonly aimWeight: Record<Side, number> = { L: 0, R: 0 };
  private readonly aimHold: Record<Side, number> = { L: 0, R: 0 };
  readonly aimPoint = new THREE.Vector3();
  private readonly reactorMats: THREE.MeshStandardMaterial[] = [];
  private bank = 0;
  private lean = new THREE.Vector2();
  private readonly qHover = new THREE.Quaternion();
  private readonly qFlight = new THREE.Quaternion();
  /** angular velocity (rad/s) of the uncontrolled tumble after the suit is destroyed */
  readonly tumble = new THREE.Vector3();
  private readonly tumbleRot = new THREE.Quaternion();

  constructor(scene: THREE.Scene, assets: Assets, textures: FxTextures) {
    const gltf = assets.gltf('player');
    this.root = gltf.scene;
    this.root.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) {
        m.castShadow = true;
        m.receiveShadow = true;
        const mat = m.material as THREE.MeshStandardMaterial;
        if (mat.name === 'Emissive_Cyan' && !this.reactorMats.includes(mat)) this.reactorMats.push(mat);
      }
    });
    scene.add(this.root);
    this.mixer = new THREE.AnimationMixer(this.root);
    const byPose = new Map<string, THREE.KeyframeTrack[]>();
    for (const clip of gltf.animations) {
      const pose = clip.name.split('__')[0];
      if (!byPose.has(pose)) byPose.set(pose, []);
      byPose.get(pose)!.push(...clip.tracks);
    }
    const action = (name: string) => {
      const a = this.mixer.clipAction(new THREE.AnimationClip(name, -1, byPose.get(name) ?? []));
      a.play();
      a.setEffectiveWeight(0);
      return a;
    };
    this.actions = { standing: action('standing'), hover: action('hover'), flight: action('flight') };
    const n = (name: string) => Assets.node(this.root, name);
    const sides = <T>(f: (s: Side) => T): Record<Side, T> => ({ L: f('L'), R: f('R') });
    this.arm = sides((s) => n(`Arm_${s}`));
    this.forearm = sides((s) => n(`Forearm_${s}`));
    this.hand = sides((s) => n(`Hand_${s}`));
    this.palm = sides((s) => n(`PalmReactor_${s}`));
    this.launcher = sides((s) => n(`Launcher_${s}`));
    this.miniLauncher = sides((s) => n(`MiniLauncher_${s}`));
    const cyan = new THREE.Color(0.35, 0.8, 1.0);
    this.palmFlame = sides((s) => new ThrusterFlame(this.palm[s], 0.028, 0.55, cyan, textures.soft, s === 'L' ? 1 : 2));
    this.footFlame = sides((s) => new ThrusterFlame(n(`FootThruster_${s}`), 0.036, 0.95, cyan, textures.soft, s === 'L' ? 3 : 4));
  }

  /** Raise an arm toward the aim point (repulsor shot). */
  fire(side: Side) {
    this.aimHold[side] = 0.35;
    this.aimWeight[side] = Math.max(this.aimWeight[side], 0.85);
  }

  palmWorld(side: Side, out: THREE.Vector3) {
    return this.palm[side].getWorldPosition(out);
  }

  update(dt: number, s: VisualState, position: THREE.Vector3, alive: boolean) {
    // pose weights
    const stand = s.standBlend;
    const flight = (1 - stand) * s.flightBlend;
    const hover = Math.max(0, 1 - stand - flight);
    this.actions.standing.setEffectiveWeight(stand);
    this.actions.hover.setEffectiveWeight(hover);
    this.actions.flight.setEffectiveWeight(flight);

    // body orientation: upright + lean while hovering, aim aligned + bank while flying
    _f.set(0, 0, 1).applyQuaternion(s.aim);
    const yaw = Math.atan2(_f.x, _f.z);
    _q.setFromAxisAngle(UP, yaw);
    const localAccel = _v.copy(s.accel).applyQuaternion(_q2.copy(_q).invert());
    const localVel = _v2.copy(s.vel).applyQuaternion(_q2);
    this.lean.x += (clamp(localAccel.z * 0.012 + localVel.z * 0.006, -0.35, 0.45) - this.lean.x) * damp(5, dt);
    this.lean.y += (clamp(-localAccel.x * 0.012 - localVel.x * 0.008, -0.4, 0.4) - this.lean.y) * damp(5, dt);
    this.qHover.copy(_q)
      .multiply(_q2.setFromAxisAngle(new THREE.Vector3(1, 0, 0), this.lean.x))
      .multiply(_q2.setFromAxisAngle(FORWARD, this.lean.y));
    const bankTarget = clamp(-s.yawRate * 0.3 + s.strafe * 0.35, -0.9, 0.9);
    this.bank += (bankTarget - this.bank) * damp(4, dt);
    this.qFlight.copy(s.aim).multiply(_q2.setFromAxisAngle(FORWARD, this.bank));
    this.root.quaternion.slerpQuaternions(this.qHover, this.qFlight, s.flightBlend);
    if (!alive) {
      _q2.setFromEuler(_e.set(this.tumble.x * dt, this.tumble.y * dt, this.tumble.z * dt));
      this.tumbleRot.multiply(_q2);
      this.root.quaternion.multiply(this.tumbleRot);
    } else {
      this.tumbleRot.identity();
    }
    this.root.position.copy(position);
    this.mixer.update(dt);
    this.root.updateMatrixWorld(true);
    this.applyArmAim(dt);

    // thrusters: feet carry the weight while hovering, palms stabilise; everything flares on boost
    const base = stand > 0.5 ? 0 : 0.35;
    const k = alive ? Math.min(1, base + s.thrust * 0.8 + (s.boosting ? 0.4 : 0)) : 0.15;
    for (const side of ['L', 'R'] as Side[]) {
      this.footFlame[side].set(stand > 0.5 ? 0 : k, s.time);
      this.palmFlame[side].set(stand > 0.5 || this.aimWeight[side] > 0.3 ? 0 : k * 0.85, s.time);
    }
    const flicker = s.armor < 25 ? (Math.sin(s.time * 40) > 0.6 ? 0.3 : 1) : 1;
    for (const m of this.reactorMats) m.emissiveIntensity = (3.4 + Math.sin(s.time * 3) * 0.6 + s.thrust * 1.6) * flicker;
  }

  private applyArmAim(dt: number) {
    for (const side of ['L', 'R'] as Side[]) {
      this.aimHold[side] -= dt;
      const target = this.aimHold[side] > 0 ? 1 : 0;
      this.aimWeight[side] += (target - this.aimWeight[side]) * damp(target > 0 ? 25 : 5, dt);
      const w = this.aimWeight[side];
      if (w < 0.01) continue;
      const arm = this.arm[side];
      this.forearm[side].quaternion.slerp(IDENT, w);
      this.hand[side].quaternion.slerp(HAND_AIM, w);
      const shoulder = arm.getWorldPosition(_v);
      const desired = _v2.subVectors(this.aimPoint, shoulder).normalize();
      const armWorld = arm.getWorldQuaternion(_q);
      const current = _f.copy(DOWN).applyQuaternion(armWorld);
      _q2.setFromUnitVectors(current, desired).multiply(armWorld);
      const local = arm.parent!.getWorldQuaternion(_pq).invert().multiply(_q2);
      arm.quaternion.slerp(local, w);
      arm.updateMatrixWorld(true);
    }
  }

  setVisible(v: boolean) {
    this.root.visible = v;
  }
}
