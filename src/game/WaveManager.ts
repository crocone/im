import type { GameContext } from './Context';
import { TUNING } from './constants';

interface WaveDef {
  drones: number;
  reinforcements: number;
  turrets: number;
  aggression: number;
  boss?: boolean;
  subtitle: string;
}

const WAVES: WaveDef[] = [
  { drones: 4, reinforcements: 0, turrets: 0, aggression: 0.85, subtitle: 'DRONE SCOUTS INBOUND' },
  { drones: 5, reinforcements: 3, turrets: 0, aggression: 1.0, subtitle: 'DRONE SWARM' },
  { drones: 5, reinforcements: 0, turrets: 3, aggression: 1.05, subtitle: 'ROOFTOP BATTERIES DEPLOYING' },
  { drones: 6, reinforcements: 5, turrets: 3, aggression: 1.25, subtitle: 'HEAVY PRESSURE' },
  { drones: 2, reinforcements: 0, turrets: 0, aggression: 1.1, boss: true, subtitle: 'WARNING — ARMORED BEHEMOTH' },
];

export type WaveState = 'idle' | 'intro' | 'active' | 'recovery' | 'victory';

/** Wave progression: intro banner -> spawn -> fight -> clear -> recovery -> next wave. */
export class WaveManager {
  wave = 0;
  state: WaveState = 'idle';
  onVictory: (() => void) | null = null;
  private timer = 0;
  private pending = 0;
  private reinforceTimer = 0;

  constructor(private readonly ctx: GameContext) {}

  get total() {
    return WAVES.length;
  }

  reset() {
    this.wave = 0;
    this.state = 'idle';
    this.timer = 0;
    this.pending = 0;
  }

  start() {
    this.wave = 0;
    this.next(3);
  }

  private next(delay: number) {
    this.wave++;
    const def = WAVES[this.wave - 1];
    this.state = 'intro';
    this.timer = delay;
    this.ctx.hud.banner(`WAVE ${this.wave}`, def.subtitle);
    this.ctx.audio.waveStart(!!def.boss);
  }

  private spawn() {
    const def = WAVES[this.wave - 1];
    const { enemies } = this.ctx;
    enemies.spawnDroneWave(def.drones, def.aggression);
    if (def.turrets) enemies.spawnTurrets(def.turrets);
    if (def.boss) {
      const boss = enemies.spawnBoss();
      boss.onDefeated = () => this.victory();
      this.ctx.hud.toast('BEHEMOTH INBOUND — BREAK ITS SHIELD WITH MISSILES', 4, 'danger');
    }
    this.pending = def.reinforcements;
    this.reinforceTimer = 14;
    this.state = 'active';
  }

  private victory() {
    this.state = 'victory';
    this.timer = 4;
  }

  update(dt: number) {
    const { enemies, player, hud } = this.ctx;
    switch (this.state) {
      case 'intro':
        this.timer -= dt;
        if (this.timer <= 0) this.spawn();
        break;
      case 'active': {
        const def = WAVES[this.wave - 1];
        this.reinforceTimer -= dt;
        if (this.pending > 0 && (this.reinforceTimer <= 0 || enemies.hostiles <= 2)) {
          enemies.spawnDroneWave(this.pending, def.aggression);
          hud.toast(`REINFORCEMENTS — ${this.pending} DRONES`, 2, 'warn');
          this.pending = 0;
        }
        if (!def.boss && this.pending === 0 && enemies.hostiles === 0) {
          this.state = 'recovery';
          this.timer = TUNING.waves.recovery;
          player.repair(TUNING.armor.waveRepair);
          player.refill();
          hud.banner('WAVE CLEAR', 'ARMOR REPAIRED · MUNITIONS RESTOCKED');
          this.ctx.audio.waveClear();
        }
        break;
      }
      case 'recovery':
        this.timer -= dt;
        if (this.timer <= 0) this.next(2.5);
        break;
      case 'victory':
        this.timer -= dt;
        if (this.timer <= 0) {
          this.state = 'idle';
          this.onVictory?.();
        }
        break;
      default:
        break;
    }
  }
}
