import * as THREE from 'three';
import { GLTFLoader, type GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js';
import manifest from '../assets.json';

export type AssetKey = keyof typeof manifest;

/** Loads every Blender-generated GLB listed in src/assets.json. */
export class Assets {
  private readonly gltfs = new Map<AssetKey, GLTF>();

  async load(onProgress: (fraction: number, label: string) => void) {
    const loader = new GLTFLoader();
    const entries = Object.entries(manifest) as [AssetKey, { file: string }][];
    let done = 0;
    await Promise.all(
      entries.map(async ([key, spec]) => {
        const url = `${import.meta.env.BASE_URL}assets/${spec.file}`;
        try {
          const gltf = await loader.loadAsync(url);
          this.prepare(gltf);
          this.gltfs.set(key, gltf);
        } catch (err) {
          throw new Error(`Failed to load ${url}: ${(err as Error).message ?? err}`);
        }
        done++;
        onProgress(done / entries.length, spec.file);
      }),
    );
  }

  private prepare(gltf: GLTF) {
    gltf.scene.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      for (const m of mats) {
        const std = m as THREE.MeshStandardMaterial;
        if (std.isMeshStandardMaterial && std.emissiveIntensity > 0 && std.emissive.getHex() !== 0) {
          // keep emissive parts crisp under fog
          std.fog = true;
        }
      }
    });
  }

  gltf(key: AssetKey): GLTF {
    const g = this.gltfs.get(key);
    if (!g) throw new Error(`asset not loaded: ${key}`);
    return g;
  }

  /** The loaded scene graph (shared; clone before adding to the world more than once). */
  scene(key: AssetKey): THREE.Group {
    return this.gltf(key).scene;
  }

  /** Deep clone sharing geometry and materials. */
  clone(key: AssetKey): THREE.Object3D {
    return this.gltf(key).scene.clone(true);
  }

  /** Find a named node inside an object hierarchy (throws if missing: assets are verified). */
  static node<T extends THREE.Object3D = THREE.Object3D>(root: THREE.Object3D, name: string): T {
    const n = root.getObjectByName(name);
    if (!n) throw new Error(`node "${name}" not found in ${root.name}`);
    return n as T;
  }
}
