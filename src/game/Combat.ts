import * as THREE from 'three';
import type { HitSource, Hittable } from '../physics/Physics';
import type { GameContext } from './Context';
import { clamp } from './math';

export interface ExplosionParams {
  radius: number;
  damage: number;
  scale: number;
  source: HitSource;
  direct?: Hittable | null;
  shockwave?: boolean;
}

const _dir = new THREE.Vector3();

/** Resolves explosions: visuals, sound, camera shake, direct + splash damage, props and debris. */
export class Combat {
  constructor(private readonly ctx: GameContext) {}

  explosion(pos: THREE.Vector3, p: ExplosionParams) {
    const { fx, player, enemies, cam } = this.ctx;
    fx.explosions.spawn(pos, { scale: p.scale, shockwave: p.shockwave });
    this.ctx.audio.explosion(pos, p.scale);
    const dPlayer = pos.distanceTo(player.position);
    cam.shake(clamp(p.scale * 0.45 * (1 - dPlayer / (140 * Math.sqrt(p.scale))), 0, 0.85));

    if (p.direct && p.damage > 0) {
      _dir.subVectors(pos, player.position).normalize();
      p.direct.hit({ damage: p.damage, point: pos.clone(), dir: _dir.clone(), source: p.source, impulse: 0 });
    }
    const friendly = p.source === 'enemy';
    if (p.damage > 0 && !friendly) {
      // splash against enemies (the boss shield soaks splash while it is up)
      for (const e of enemies.list) {
        if (!e.alive || e === p.direct) continue;
        if (e.kind === 'boss' && p.direct && p.direct.kind === 'shield') continue;
        const d = e.position.distanceTo(pos) - e.radius;
        if (d > p.radius) continue;
        const falloff = 1 - Math.max(0, d) / p.radius;
        _dir.subVectors(e.position, pos).normalize();
        e.hit({ damage: p.damage * 0.6 * falloff, point: pos.clone(), dir: _dir.clone(), source: p.source, impulse: 0 });
      }
      // chain-detonate hostile missiles caught in the blast
      for (const m of this.ctx.missiles.incoming()) {
        if (m.position.distanceTo(pos) < p.radius) m.explode(null, true);
      }
    }
    if (friendly && p.damage > 0 && player.alive) {
      const d = dPlayer - 1;
      if (d < p.radius && !p.direct) {
        const falloff = 1 - Math.max(0, d) / p.radius;
        _dir.subVectors(player.position, pos).normalize();
        player.hit({ damage: p.damage * falloff, point: player.position.clone(), dir: _dir.clone(), source: p.source, impulse: 0 });
        player.flight.vel.addScaledVector(_dir, 18 * falloff);
      }
    }
    // the city takes damage from every blast
    this.ctx.destruction.explosion(pos, p.radius * 1.2, Math.max(p.damage, p.scale * 45));
    this.ctx.debris.explosionImpulse(pos, p.radius * 2.5, 6 + p.scale * 5);
  }
}
