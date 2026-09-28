import * as THREE from 'three';

const beamVertex = /* glsl */ `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

const beamFragment = /* glsl */ `
uniform vec3 uColor;
uniform float uAlpha;
uniform float uTime;
varying vec2 vUv;
void main() {
  // uv.x wraps around the cylinder: brighter at the silhouette centre facing the camera
  float around = abs(sin(vUv.x * 3.14159265));
  float pulse = 0.75 + 0.25 * sin(vUv.y * 60.0 - uTime * 80.0);
  float fadeEnds = smoothstep(0.0, 0.04, vUv.y) * smoothstep(1.0, 0.9, vUv.y);
  gl_FragColor = vec4(uColor * (0.6 + around) * pulse, uAlpha * fadeEnds);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

interface Beam {
  core: THREE.Mesh;
  glow: THREE.Mesh;
  age: number;
  life: number;
  width: number;
}

const _dir = new THREE.Vector3();
const _up = new THREE.Vector3(0, 1, 0);

/** Pooled repulsor / energy beams: two additive cylinders stretched between muzzle and impact. */
export class BeamFx {
  private readonly pool: Beam[] = [];
  private readonly geometry = new THREE.CylinderGeometry(1, 1, 1, 10, 1, true).translate(0, 0.5, 0);

  constructor(scene: THREE.Scene, size = 16) {
    for (let i = 0; i < size; i++) {
      const mk = (color: THREE.Color, order: number) => {
        const m = new THREE.Mesh(
          this.geometry,
          new THREE.ShaderMaterial({
            uniforms: { uColor: { value: color }, uAlpha: { value: 0 }, uTime: { value: 0 } },
            vertexShader: beamVertex,
            fragmentShader: beamFragment,
            transparent: true,
            depthWrite: false,
            blending: THREE.AdditiveBlending,
          }),
        );
        m.visible = false;
        m.frustumCulled = false;
        m.renderOrder = order;
        scene.add(m);
        return m;
      };
      this.pool.push({
        core: mk(new THREE.Color(2.2, 3.4, 4.0), 31),
        glow: mk(new THREE.Color(0.25, 0.8, 1.6), 30),
        age: 1,
        life: 1,
        width: 1,
      });
    }
  }

  fire(from: THREE.Vector3, to: THREE.Vector3, width = 0.09, life = 0.13, color?: THREE.Color) {
    const b = this.pool.find((p) => p.age >= p.life) ?? this.pool[0];
    _dir.subVectors(to, from);
    const len = _dir.length();
    if (len < 0.01) return;
    _dir.divideScalar(len);
    for (const m of [b.core, b.glow]) {
      m.position.copy(from);
      m.quaternion.setFromUnitVectors(_up, _dir);
      m.visible = true;
      m.scale.set(1, len, 1);
    }
    const mat = b.glow.material as THREE.ShaderMaterial;
    if (color) mat.uniforms.uColor.value.copy(color);
    else mat.uniforms.uColor.value.setRGB(0.25, 0.8, 1.6);
    b.age = 0;
    b.life = life;
    b.width = width;
    this.apply(b);
  }

  private apply(b: Beam) {
    const t = Math.min(1, b.age / b.life);
    const w = b.width * (1 - t * 0.6);
    b.core.scale.x = b.core.scale.z = w * 0.45;
    b.glow.scale.x = b.glow.scale.z = w * 2.4;
    (b.core.material as THREE.ShaderMaterial).uniforms.uAlpha.value = (1 - t) * 1.0;
    (b.glow.material as THREE.ShaderMaterial).uniforms.uAlpha.value = (1 - t) * 0.55;
  }

  update(dt: number, time: number) {
    for (const b of this.pool) {
      if (b.age >= b.life) continue;
      b.age += dt;
      if (b.age >= b.life) {
        b.core.visible = b.glow.visible = false;
        continue;
      }
      (b.core.material as THREE.ShaderMaterial).uniforms.uTime.value = time;
      (b.glow.material as THREE.ShaderMaterial).uniforms.uTime.value = time;
      this.apply(b);
    }
  }

  clear() {
    for (const b of this.pool) {
      b.age = b.life;
      b.core.visible = b.glow.visible = false;
    }
  }
}
