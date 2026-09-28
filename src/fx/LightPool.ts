import * as THREE from 'three';

interface Slot {
  light: THREE.PointLight;
  peak: number;
  age: number;
  life: number;
}

/**
 * A fixed set of point lights reused for muzzle flashes and explosions. Lights are created
 * once (so shader programs never recompile) and sit at zero intensity when idle.
 */
export class LightPool {
  private readonly slots: Slot[] = [];

  constructor(scene: THREE.Scene, count = 6) {
    for (let i = 0; i < count; i++) {
      const light = new THREE.PointLight(0xffffff, 0, 60, 2);
      light.castShadow = false;
      scene.add(light);
      this.slots.push({ light, peak: 0, age: 1, life: 1 });
    }
  }

  flash(pos: THREE.Vector3, color: THREE.ColorRepresentation, intensity: number, range: number, life: number) {
    // reuse the dimmest light
    let best = this.slots[0];
    let bestValue = Infinity;
    for (const s of this.slots) {
      const v = s.light.intensity;
      if (v < bestValue) {
        bestValue = v;
        best = s;
      }
    }
    best.light.position.copy(pos);
    best.light.color.set(color);
    best.light.distance = range;
    best.peak = intensity;
    best.age = 0;
    best.life = life;
    best.light.intensity = intensity;
  }

  update(dt: number) {
    for (const s of this.slots) {
      if (s.light.intensity <= 0) continue;
      s.age += dt;
      const t = s.age / s.life;
      s.light.intensity = t >= 1 ? 0 : s.peak * (1 - t) * (1 - t);
    }
  }

  clear() {
    for (const s of this.slots) s.light.intensity = 0;
  }
}
