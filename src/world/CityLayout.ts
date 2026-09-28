import { TUNING } from '../game/constants';
import { seeded } from '../game/math';

export type BlockKind = 'dense' | 'landmark' | 'park' | 'plaza';
export type LotUse =
  | { use: 'building'; type: number; rot: number; scaleY: number }
  | { use: 'plaza' }
  | { use: 'parking' };

export interface Lot {
  x: number;
  z: number;
  lot: LotUse;
}

export interface Block {
  i: number;
  j: number;
  x: number;
  z: number;
  kind: BlockKind;
  lots: Lot[];
}

const SPECIAL: Record<string, BlockKind> = {
  '4,4': 'landmark',
  '1,6': 'park',
  '6,1': 'park',
  '7,7': 'park',
  '2,2': 'park',
  '4,1': 'plaza',
  '1,4': 'plaza',
  '6,5': 'plaza',
};

const TALL = [1, 2, 3, 5, 7, 9, 1, 2];
const MID = [1, 2, 4, 5, 6, 9, 4, 6];
const LOW = [4, 6, 8, 9, 8, 4, 6];
const TOWERS = new Set([1, 2, 5, 7, 9]);

/** Deterministic plan of the 9 x 9 block city: which module goes in which 40 m lot. */
export function planCity(seed = 1337): Block[] {
  const rnd = seeded(seed);
  const n = TUNING.city.blocks;
  const pitch = TUNING.city.pitch;
  const blocks: Block[] = [];
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const x = (i - (n - 1) / 2) * pitch;
      const z = (j - (n - 1) / 2) * pitch;
      const kind = SPECIAL[`${i},${j}`] ?? 'dense';
      const ring = Math.max(Math.abs(i - 4), Math.abs(j - 4));
      const lots: Lot[] = [];
      for (const [lx, lz] of [[-20, -20], [20, -20], [-20, 20], [20, 20]]) {
        let lot: LotUse;
        if (kind === 'landmark') {
          if (lx < 0 && lz < 0) lot = { use: 'building', type: 3, rot: 0, scaleY: 1 };
          else if (lx > 0 && lz > 0) lot = { use: 'building', type: 7, rot: 0, scaleY: 1 };
          else lot = { use: 'plaza' };
        } else if (kind === 'dense') {
          if (rnd() < 0.07) lot = { use: 'parking' };
          else {
            const pool = ring <= 1 ? TALL : ring === 2 ? MID : LOW;
            const type = pool[Math.floor(rnd() * pool.length)];
            const scaleY = TOWERS.has(type) ? 0.85 + rnd() * 0.4 : 1;
            lot = { use: 'building', type, rot: Math.floor(rnd() * 4), scaleY };
          }
        } else {
          lot = { use: 'plaza' };
        }
        lots.push({ x: x + lx, z: z + lz, lot });
      }
      blocks.push({ i, j, x, z, kind, lots });
    }
  }
  return blocks;
}
