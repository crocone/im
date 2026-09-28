import { Assets } from './game/Assets';
import { Game } from './game/Game';
import { Overlays } from './hud/Overlays';
import { Physics } from './physics/Physics';

function webglAvailable() {
  try {
    const c = document.createElement('canvas');
    return !!c.getContext('webgl2');
  } catch {
    return false;
  }
}

async function boot() {
  const overlays = new Overlays();
  overlays.show('loading');
  if (!webglAvailable()) {
    overlays.error('WebGL 2 is not available in this browser. Please use a current desktop Chrome, Edge or Firefox.');
    return;
  }
  try {
    overlays.progress(0.02, 'starting physics engine');
    const physics = await Physics.create();
    const assets = new Assets();
    await assets.load((f, label) => overlays.progress(0.05 + f * 0.85, label));
    overlays.progress(0.95, 'building city');
    await new Promise((r) => setTimeout(r, 30));
    const canvas = document.getElementById('game') as HTMLCanvasElement;
    const game = new Game(canvas, physics, assets, overlays);
    game.start();
    overlays.show('menu');
  } catch (err) {
    console.error(err);
    overlays.error(err instanceof Error ? err.message : String(err));
  }
}

void boot();
