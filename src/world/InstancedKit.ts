import * as THREE from 'three';

/**
 * Turns one authored GLB hierarchy into a set of InstancedMeshes (one per mesh primitive),
 * so an entire city of repeated modules renders in a handful of draw calls.
 */
export class InstancedKit {
  readonly meshes: THREE.InstancedMesh[] = [];
  private count = 0;
  private readonly hidden = new THREE.Matrix4().makeScale(0, 0, 0);

  constructor(template: THREE.Object3D, readonly capacity: number, castShadow = true, receiveShadow = true) {
    template.updateMatrixWorld(true);
    const rootInv = template.matrixWorld.clone().invert();
    const local = new THREE.Matrix4();
    template.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      local.multiplyMatrices(rootInv, mesh.matrixWorld);
      const geometry = mesh.geometry.clone().applyMatrix4(local);
      const inst = new THREE.InstancedMesh(geometry, mesh.material, capacity);
      inst.name = `${template.name}/${mesh.name}`;
      inst.castShadow = castShadow;
      inst.receiveShadow = receiveShadow;
      inst.count = 0;
      this.meshes.push(inst);
    });
  }

  get size() {
    return this.count;
  }

  /** Add an instance. ``color`` tints only meshes using the material named ``colorMaterial``. */
  add(matrix: THREE.Matrix4, color?: THREE.Color, colorMaterial?: string): number {
    if (this.count >= this.capacity) throw new Error('InstancedKit capacity exceeded');
    const i = this.count++;
    for (const m of this.meshes) {
      m.setMatrixAt(i, matrix);
      if (color && (!colorMaterial || (m.material as THREE.Material).name === colorMaterial)) m.setColorAt(i, color);
      m.count = this.count;
    }
    return i;
  }

  setMatrix(i: number, matrix: THREE.Matrix4) {
    for (const m of this.meshes) {
      m.setMatrixAt(i, matrix);
      m.instanceMatrix.needsUpdate = true;
    }
  }

  hide(i: number) {
    this.setMatrix(i, this.hidden);
  }

  finish() {
    for (const m of this.meshes) {
      m.instanceMatrix.needsUpdate = true;
      if (m.instanceColor) m.instanceColor.needsUpdate = true;
      m.computeBoundingSphere();
      m.visible = this.count > 0;
    }
  }

  addTo(parent: THREE.Object3D) {
    for (const m of this.meshes) parent.add(m);
  }
}
