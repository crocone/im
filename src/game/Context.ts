import type * as THREE from 'three';
import type { EnemyBolts } from '../weapons/EnemyBolts';
import type { EnemyManager } from '../enemies/EnemyManager';
import type { FxSystem } from '../fx/FxSystem';
import type { Hud } from '../hud/Hud';
import type { Physics } from '../physics/Physics';
import type { PlayerCamera } from '../player/PlayerCamera';
import type { PlayerController } from '../player/PlayerController';
import type { MiniMissileSystem } from '../weapons/MiniMissileSystem';
import type { MissileSystem } from '../weapons/MissileSystem';
import type { RepulsorSystem } from '../weapons/RepulsorSystem';
import type { TargetingSystem } from '../weapons/TargetingSystem';
import type { CityBuilder } from '../world/CityBuilder';
import type { DebrisSystem } from '../world/DebrisSystem';
import type { DestructionSystem } from '../world/DestructionSystem';
import type { Assets } from './Assets';
import type { AudioSystem } from './AudioSystem';
import type { Combat } from './Combat';
import type { Input } from './Input';
import type { Score } from './Score';
import type { WaveManager } from './WaveManager';

/** Shared references between gameplay systems (filled in by Game during construction). */
export interface GameContext {
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  physics: Physics;
  assets: Assets;
  input: Input;
  fx: FxSystem;
  audio: AudioSystem;
  hud: Hud;
  city: CityBuilder;
  player: PlayerController;
  cam: PlayerCamera;
  targeting: TargetingSystem;
  repulsors: RepulsorSystem;
  missiles: MissileSystem;
  minis: MiniMissileSystem;
  bolts: EnemyBolts;
  enemies: EnemyManager;
  destruction: DestructionSystem;
  debris: DebrisSystem;
  combat: Combat;
  score: Score;
  waves: WaveManager;
  /** seconds of gameplay time (pauses with the game) */
  time: number;
}
