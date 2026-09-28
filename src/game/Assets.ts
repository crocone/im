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
    this.applyMaterialLibrary();
  }

  /**
   * City modules ship untextured placeholder materials; the shared, fully textured versions live
   * once in city_materials.glb and are swapped in by name, so each facade / roof texture set is
   * downloaded and uploaded to the GPU a single time.
   */
  private applyMaterialLibrary() {
    const lib = this.gltfs.get('cityMaterials');
    if (!lib) return;
    const byName = new Map<string, THREE.Material>();
    lib.scene.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (mesh.isMesh) for (const m of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) byName.set(m.name, m);
    });
    for (const [key, gltf] of this.gltfs) {
      if (key === 'cityMaterials') continue;
      gltf.scene.traverse((o) => {
        const mesh = o as THREE.Mesh;
        if (!mesh.isMesh) return;
        if (Array.isArray(mesh.material)) mesh.material = mesh.material.map((m) => byName.get(m.name) ?? m);
        else mesh.material = byName.get(mesh.material.name) ?? mesh.material;
      });
    }
  }

  private prepare(gltf: GLTF) {
    gltf.scene.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      for (const m of mats) {
        const std = m as THREE.MeshStandardMaterial;
        // facades, roads and armour are mostly seen at grazing angles: anisotropic filtering keeps them crisp
        for (const t of [std.map, std.normalMap, std.roughnessMap, std.emissiveMap]) if (t) t.anisotropy = 8;
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
