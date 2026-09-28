import * as THREE from 'three';
import { seeded } from '../game/math';

function canvasTexture(size: number, draw: (ctx: CanvasRenderingContext2D, s: number) => void): THREE.CanvasTexture {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const ctx = c.getContext('2d')!;
  draw(ctx, size);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.NoColorSpace;
  t.generateMipmaps = true;
  t.minFilter = THREE.LinearMipmapLinearFilter;
  return t;
}

function radial(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, stops: [number, string][]) {
  const g = ctx.createRadialGradient(x, y, 0, x, y, r);
  for (const [o, c] of stops) g.addColorStop(o, c);
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
  ctx.fill();
}

/** Procedural sprite textures for particles and flashes (generated at startup, no image files). */
export class FxTextures {
  readonly soft = canvasTexture(64, (ctx, s) =>
    radial(ctx, s / 2, s / 2, s / 2, [[0, 'rgba(255,255,255,1)'], [0.35, 'rgba(255,255,255,0.55)'], [1, 'rgba(255,255,255,0)']]),
  );

  readonly hard = canvasTexture(32, (ctx, s) =>
    radial(ctx, s / 2, s / 2, s / 2, [[0, 'rgba(255,255,255,1)'], [0.5, 'rgba(255,255,255,0.9)'], [1, 'rgba(255,255,255,0)']]),
  );

  readonly smoke = canvasTexture(128, (ctx, s) => {
    const rnd = seeded(7);
    for (let i = 0; i < 26; i++) {
      const a = rnd() * Math.PI * 2;
      const d = rnd() * s * 0.22;
      const r = s * (0.14 + rnd() * 0.2);
      const v = 200 + Math.floor(rnd() * 55);
      radial(ctx, s / 2 + Math.cos(a) * d, s / 2 + Math.sin(a) * d, r, [
        [0, `rgba(${v},${v},${v},0.34)`],
        [1, `rgba(${v},${v},${v},0)`],
      ]);
    }
  });

  /** soft, low-contrast puff for continuous missile trails */
  readonly puff = canvasTexture(64, (ctx, s) => {
    radial(ctx, s / 2, s / 2, s / 2, [[0, 'rgba(235,235,235,0.55)'], [0.45, 'rgba(225,225,225,0.35)'], [1, 'rgba(220,220,220,0)']]);
    const rnd = seeded(11);
    for (let i = 0; i < 10; i++) {
      const a = rnd() * Math.PI * 2;
      const d = rnd() * s * 0.16;
      radial(ctx, s / 2 + Math.cos(a) * d, s / 2 + Math.sin(a) * d, s * (0.2 + rnd() * 0.12), [[0, 'rgba(255,255,255,0.12)'], [1, 'rgba(255,255,255,0)']]);
    }
  });

  readonly flare = canvasTexture(128, (ctx, s) => {
    radial(ctx, s / 2, s / 2, s / 2, [[0, 'rgba(255,255,255,1)'], [0.18, 'rgba(255,255,255,0.7)'], [0.5, 'rgba(255,255,255,0.12)'], [1, 'rgba(255,255,255,0)']]);
    ctx.globalCompositeOperation = 'lighter';
    for (const angle of [0, Math.PI / 2, Math.PI / 4, -Math.PI / 4]) {
      ctx.save();
      ctx.translate(s / 2, s / 2);
      ctx.rotate(angle);
      const long = angle === 0 || angle === Math.PI / 2;
      const g = ctx.createLinearGradient(-s / 2, 0, s / 2, 0);
      g.addColorStop(0, 'rgba(255,255,255,0)');
      g.addColorStop(0.5, `rgba(255,255,255,${long ? 0.8 : 0.35})`);
      g.addColorStop(1, 'rgba(255,255,255,0)');
      ctx.fillStyle = g;
      ctx.fillRect(-s / 2, long ? -2 : -1, s, long ? 4 : 2);
      ctx.restore();
    }
  });

  readonly ring = canvasTexture(128, (ctx, s) =>
    radial(ctx, s / 2, s / 2, s / 2, [[0, 'rgba(255,255,255,0)'], [0.72, 'rgba(255,255,255,0)'], [0.86, 'rgba(255,255,255,1)'], [1, 'rgba(255,255,255,0)']]),
  );
}
