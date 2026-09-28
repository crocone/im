import * as THREE from 'three';
import { EnemyManager } from '../enemies/EnemyManager';
import { FxSystem } from '../fx/FxSystem';
import { Hud } from '../hud/Hud';
import type { Overlays } from '../hud/Overlays';
import { Radar } from '../hud/Radar';
import { TargetMarkers } from '../hud/TargetMarkers';
import type { Physics } from '../physics/Physics';
import { PlayerCamera } from '../player/PlayerCamera';
import { PlayerController } from '../player/PlayerController';
import { EnemyBolts } from '../weapons/EnemyBolts';
import { MiniMissileSystem } from '../weapons/MiniMissileSystem';
import { MissileSystem } from '../weapons/MissileSystem';
import { RepulsorSystem } from '../weapons/RepulsorSystem';
import { TargetingSystem } from '../weapons/TargetingSystem';
import { CityBuilder } from '../world/CityBuilder';
import { DebrisSystem } from '../world/DebrisSystem';
import { DestructionSystem } from '../world/DestructionSystem';
import { Environment } from '../world/Environment';
import type { Assets } from './Assets';
import { AudioSystem } from './AudioSystem';
import { Combat } from './Combat';
import type { GameContext } from './Context';
import { TUNING } from './constants';
import { Input } from './Input';
import { GameRenderer } from './Renderer';
import { Score } from './Score';
import { WaveManager } from './WaveManager';

export type GameState = 'menu' | 'playing' | 'paused' | 'dead' | 'victory';

const SPAWN_YAW = Math.PI; // face north (-Z), toward the low sun

/** Top-level orchestration: builds every system, runs the frame loop and the game state flow. */
export class Game {
  readonly ctx: GameContext;
  state: GameState = 'menu';
  private readonly renderer: GameRenderer;
  private readonly env: Environment;
  private readonly markers: TargetMarkers;
  private readonly radar: Radar;
  private readonly clock = new THREE.Timer();
  private readonly spawn = new THREE.Vector3();
  private elapsed = 0;
  private menuTime = 0;

  constructor(canvas: HTMLCanvasElement, physics: Physics, assets: Assets, private readonly overlays: Overlays) {
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.3, 9000);
    this.renderer = new GameRenderer(canvas, scene, camera);
    const ctx = { scene, camera, physics, assets, time: 0 } as GameContext;
    this.ctx = ctx;
    ctx.input = new Input(canvas);
    ctx.audio = new AudioSystem();
    ctx.hud = new Hud();
    this.env = new Environment(scene, this.renderer.renderer, assets);
    ctx.fx = new FxSystem(scene);
    ctx.city = new CityBuilder(scene, physics, assets);
    ctx.debris = new DebrisSystem(ctx);
    ctx.destruction = new DestructionSystem(ctx, ctx.city.props.destructibles);
    ctx.combat = new Combat(ctx);
    ctx.score = new Score(ctx);
    ctx.player = new PlayerController(ctx);
    ctx.cam = new PlayerCamera(ctx, camera);
    ctx.targeting = new TargetingSystem(ctx);
    ctx.repulsors = new RepulsorSystem(ctx);
    ctx.missiles = new MissileSystem(ctx);
    ctx.minis = new MiniMissileSystem(ctx);
    ctx.bolts = new EnemyBolts(ctx);
    ctx.enemies = new EnemyManager(ctx);
    ctx.waves = new WaveManager(ctx);
    this.markers = new TargetMarkers(ctx.hud.markerLayer);
    this.radar = new Radar(ctx.hud.radarCanvas);
    this.spawn.copy(ctx.city.spawn).setY(ctx.city.spawn.y + 1.05);
    ctx.player.reset(this.spawn, SPAWN_YAW);
    ctx.player.onDestroyed = () => this.defeat();
    ctx.waves.onVictory = () => this.victory();
    ctx.input.onUnlock = () => {
      if (this.state === 'playing') this.pause();
    };
    overlays.onStart = () => this.newGame();
    overlays.onResume = () => this.resume();
    overlays.onRestart = () => this.newGame();
    (window as unknown as { armoredFlight: unknown }).armoredFlight = { game: this, ctx };
  }

  start() {
    const frame = (now: number) => {
      requestAnimationFrame(frame);
      this.clock.update(now);
      this.frame();
    };
    requestAnimationFrame(frame);
  }

  private reset() {
    const c = this.ctx;
    c.enemies.clear();
    c.missiles.reset();
    c.minis.reset();
    c.bolts.clear();
    c.debris.clear();
    c.destruction.reset();
    c.fx.clear();
    c.score.reset();
    c.waves.reset();
    c.targeting.reset();
    c.repulsors.reset();
    c.player.reset(this.spawn, SPAWN_YAW);
    c.cam.snap();
    c.hud.boss(false);
    this.markers.clear();
    this.elapsed = 0;
  }

  newGame() {
    this.ctx.audio.init();
    this.ctx.audio.click();
    this.reset();
    this.state = 'playing';
    this.overlays.show(null);
    this.ctx.hud.setVisible(true);
    this.ctx.input.requestLock();
    this.ctx.waves.start();
    this.ctx.hud.toast('SPACE TO LIFT OFF · F FLIGHT MODE · H CONTROLS', 5);
  }

  private pause(overlay: 'pause' | 'help' = 'pause') {
    this.state = 'paused';
    this.overlays.show(overlay);
    this.ctx.audio.suspend();
    this.ctx.input.releaseLock();
  }

  private resume() {
    this.ctx.audio.init();
    this.state = 'playing';
    this.overlays.show(null);
    this.ctx.input.requestLock();
  }

  private defeat() {
    if (this.state !== 'playing') return;
    this.state = 'dead';
    this.ctx.audio.stinger(false);
    this.overlays.stats('defeat', this.stats());
    this.overlays.show('defeat');
    this.ctx.input.releaseLock();
  }

  private victory() {
    if (this.state !== 'playing') return;
    this.state = 'victory';
    this.ctx.audio.stinger(true);
    this.overlays.stats('victory', this.stats());
    this.overlays.show('victory');
    this.ctx.input.releaseLock();
  }

  private stats() {
    const s = this.ctx.score;
    const t = Math.round(this.elapsed);
    return [
      `SCORE  ${s.value.toLocaleString('en-US')}`,
      `WAVE REACHED  ${this.ctx.waves.wave} / ${this.ctx.waves.total}`,
      `HOSTILES DESTROYED  ${s.kills}`,
      `MISSILES INTERCEPTED  ${s.intercepts}`,
      `CITY PROPS WRECKED  ${s.destroyed}`,
      `TIME  ${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`,
    ];
  }

  private frame() {
    const dt = Math.min(this.clock.getDelta(), 0.05);
    this.renderer.info.reset();
    const c = this.ctx;
    if (this.state === 'playing') this.handleKeys();
    if (this.state === 'playing' || this.state === 'dead' || this.state === 'victory') this.simulate(dt);
    else if (this.state === 'menu') this.menuCamera(dt);
    c.input.endFrame();
    this.renderer.render();
  }

  private handleKeys() {
    const { input, audio, hud } = this.ctx;
    if (input.justPressed('KeyH')) this.pause('help');
    if (input.justPressed('KeyM')) hud.toast(audio.toggleMute() ? 'AUDIO MUTED' : 'AUDIO ON', 1.2);
    if (input.justPressed('KeyY')) {
      input.invertY = !input.invertY;
      hud.toast(input.invertY ? 'MOUSE Y INVERTED' : 'MOUSE Y NORMAL', 1.2);
    }
  }

  private simulate(dt: number) {
    const c = this.ctx;
    c.time += dt;
    if (this.state === 'playing') this.elapsed += dt;
    c.player.update(dt);
    c.enemies.update(dt);
    c.physics.step(dt);
    c.player.afterPhysics();
    c.cam.update(dt);
    c.player.visual.aimPoint.copy(c.cam.aimPoint);
    c.player.updateVisual(dt);
    c.targeting.update(dt);
    c.repulsors.update(dt);
    c.missiles.update(dt);
    c.minis.update(dt);
    c.bolts.update(dt);
    c.debris.update(dt);
    c.waves.update(dt);
    c.score.update(dt);
    c.fx.update(dt, c.time);
    this.env.update(dt, c.player.position);
    this.updateHud(dt);
  }

  private updateHud(dt: number) {
    const c = this.ctx;
    const p = c.player;
    const right = new THREE.Vector3(1, 0, 0).applyQuaternion(c.camera.quaternion);
    c.audio.setListener(c.camera.position, right);
    const speedFactor = Math.min(1, p.speed / TUNING.flight.boostSpeed);
    c.audio.updateLoops(dt, p.flight.thrust, p.flight.boosting, speedFactor, p.alive);
    const incoming = c.missiles.incoming().some((m) => m.position.distanceTo(p.position) < 220);
    const warning = !p.alive ? '' : p.outOfBounds ? 'RETURN TO COMBAT ZONE'
      : incoming ? 'MISSILE WARNING' : p.armor < 25 ? 'ARMOR CRITICAL' : '';
    const t = c.targeting;
    c.hud.update(dt, {
      speed: p.speed,
      altitude: p.position.y,
      mode: p.flight.mode,
      boosting: p.flight.boosting,
      armor: p.armor,
      energy: p.energy,
      missiles: p.missiles,
      missilesMax: TUNING.missiles.max,
      minis: p.minis,
      minisMax: TUNING.missiles.miniMax,
      score: c.score.value,
      combo: c.score.combo,
      wave: c.waves.wave,
      lock: t.state,
      lockName: t.current?.label ?? '',
      warning,
      speedFactor,
    });
    const aimOwner = c.cam.aimHit?.owner;
    c.hud.reticleOnEnemy(!!aimOwner && aimOwner.kind !== 'destructible' && aimOwner.kind !== 'player');
    const boss = c.enemies.boss;
    if (boss && boss.phase !== 'dead') {
      const phase = boss.phase === 'shielded' || boss.phase === 'intro' ? 'PHASE 1 — SHIELDED'
        : boss.phase === 'exposed' ? 'PHASE 2 — EXPOSED' : boss.phase === 'critical' ? 'PHASE 3 — CRITICAL' : 'DESTROYED';
      c.hud.boss(true, boss.healthFraction, boss.shield.fraction, phase);
    } else c.hud.boss(false);
    this.markers.update(c.camera, c.enemies.markerInfo(), c.enemies.markerFor(t.current), t.progress, t.state);
    const fwd = p.flight.forward(new THREE.Vector3());
    this.radar.draw(dt, p.position, fwd, c.enemies.blips());
  }

  /** Slow orbit around the landing pad behind the title screen. */
  private menuCamera(dt: number) {
    const c = this.ctx;
    this.menuTime += dt;
    c.time += dt;
    const a = this.menuTime * 0.05 + 2.2;
    c.camera.position.set(this.spawn.x + Math.cos(a) * 34, this.spawn.y + 9, this.spawn.z + Math.sin(a) * 34);
    c.camera.lookAt(this.spawn.x, this.spawn.y + 1, this.spawn.z);
    c.player.updateVisual(dt);
    c.fx.update(dt, c.time);
    this.env.update(dt, this.spawn);
  }
}
