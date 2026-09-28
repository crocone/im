import type * as THREE from 'three';
import type { GameContext } from './Context';
import { SCORE } from './constants';

/** Score with a kill/destruction combo multiplier that decays after a short window. */
export class Score {
  value = 0;
  combo = 1;
  kills = 0;
  destroyed = 0;
  intercepts = 0;
  private comboTimer = 0;
  private bossAccum = 0;

  constructor(private readonly ctx: GameContext) {}

  reset() {
    this.value = 0;
    this.combo = 1;
    this.kills = 0;
    this.destroyed = 0;
    this.intercepts = 0;
    this.comboTimer = 0;
    this.bossAccum = 0;
  }

  private chain() {
    this.combo = this.comboTimer > 0 ? Math.min(SCORE.maxCombo, this.combo + 1) : 1;
    this.comboTimer = SCORE.comboWindow;
  }

  kill(points: number, _pos: THREE.Vector3, label: string) {
    this.chain();
    this.kills++;
    const gained = points * this.combo;
    this.value += gained;
    this.ctx.hud.toast(`${label}  +${gained}${this.combo > 1 ? `  x${this.combo}` : ''}`, 1.8);
  }

  destruct(points: number, _pos: THREE.Vector3, label: string) {
    this.chain();
    this.destroyed++;
    const gained = points * this.combo;
    this.value += gained;
    this.ctx.hud.toast(`${label} DESTROYED  +${gained}`, 1.4);
  }

  intercept(_pos: THREE.Vector3) {
    this.intercepts++;
    this.value += SCORE.intercept * this.combo;
    this.ctx.hud.toast(`MISSILE INTERCEPTED  +${SCORE.intercept * this.combo}`, 1.4);
  }

  bossDamage(amount: number, _pos: THREE.Vector3) {
    this.bossAccum += amount * SCORE.bossDamage;
    const whole = Math.floor(this.bossAccum);
    this.value += whole;
    this.bossAccum -= whole;
  }

  update(dt: number) {
    if (this.comboTimer > 0) {
      this.comboTimer -= dt;
      if (this.comboTimer <= 0) this.combo = 1;
    }
  }
}
