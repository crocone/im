import * as THREE from 'three';

export interface EmitParams {
  pos: THREE.Vector3;
  vel?: THREE.Vector3;
  life: number;
  size: number;
  size1?: number;
  color: THREE.Color;
  alpha?: number;
  color1?: THREE.Color;
  alpha1?: number;
  drag?: number;
  gravity?: number;
  rot?: number;
  spin?: number;
}

const vertex = /* glsl */ `
attribute vec3 aOffset;
attribute float aSize;
attribute vec4 aColor;
attribute float aRot;
attribute vec3 aVel;
uniform float uStretch;
varying vec2 vUv;
varying vec4 vColor;
varying float vFogDepth;
void main() {
  vUv = position.xy + 0.5;
  vColor = aColor;
  vec4 mv = modelViewMatrix * vec4(aOffset, 1.0);
  vec2 q = position.xy;
  if (uStretch > 0.0) {
    vec2 d = (viewMatrix * vec4(aVel, 0.0)).xy;
    float len = length(d);
    vec2 dir = len > 1e-4 ? d / len : vec2(1.0, 0.0);
    vec2 perp = vec2(-dir.y, dir.x);
    mv.xy += dir * q.x * (aSize + len * uStretch) + perp * q.y * aSize;
  } else {
    float c = cos(aRot);
    float s = sin(aRot);
    mv.xy += vec2(c * q.x - s * q.y, s * q.x + c * q.y) * aSize;
  }
  vFogDepth = -mv.z;
  gl_Position = projectionMatrix * mv;
}`;

const fragment = /* glsl */ `
uniform sampler2D uMap;
uniform float uAdditive;
uniform vec3 fogColor;
uniform float fogDensity;
varying vec2 vUv;
varying vec4 vColor;
varying float vFogDepth;
void main() {
  vec4 t = texture2D(uMap, vUv);
  vec4 c = vec4(vColor.rgb * t.rgb, vColor.a * t.a);
  float fog = 1.0 - exp(-fogDensity * fogDensity * vFogDepth * vFogDepth);
  if (uAdditive > 0.5) c.rgb *= (1.0 - fog);
  else c.rgb = mix(c.rgb, fogColor, fog);
  if (c.a < 0.003) discard;
  gl_FragColor = c;
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

/**
 * Pooled GPU billboards (one instanced draw call per system). CPU integrates motion; dead
 * particles are swap-removed so the live set stays packed and bounded by ``capacity``.
 */
export class Particles {
  readonly mesh: THREE.Mesh;
  private readonly geometry: THREE.InstancedBufferGeometry;
  private alive = 0;
  private readonly pos: Float32Array;
  private readonly vel: Float32Array;
  private readonly age: Float32Array;
  private readonly life: Float32Array;
  private readonly size0: Float32Array;
  private readonly size1: Float32Array;
  private readonly c0: Float32Array;
  private readonly c1: Float32Array;
  private readonly drag: Float32Array;
  private readonly grav: Float32Array;
  private readonly rot: Float32Array;
  private readonly spin: Float32Array;
  private readonly aOffset: THREE.InstancedBufferAttribute;
  private readonly aSize: THREE.InstancedBufferAttribute;
  private readonly aColor: THREE.InstancedBufferAttribute;
  private readonly aRot: THREE.InstancedBufferAttribute;
  private readonly aVel: THREE.InstancedBufferAttribute;

  constructor(readonly capacity: number, map: THREE.Texture, additive: boolean, stretch = 0) {
    const quad = new THREE.PlaneGeometry(1, 1);
    this.geometry = new THREE.InstancedBufferGeometry();
    this.geometry.index = quad.index;
    this.geometry.setAttribute('position', quad.getAttribute('position'));
    const mk = (n: number) => {
      const a = new THREE.InstancedBufferAttribute(new Float32Array(capacity * n), n);
      a.setUsage(THREE.DynamicDrawUsage);
      return a;
    };
    this.aOffset = mk(3);
    this.aSize = mk(1);
    this.aColor = mk(4);
    this.aRot = mk(1);
    this.aVel = mk(3);
    this.geometry.setAttribute('aOffset', this.aOffset);
    this.geometry.setAttribute('aSize', this.aSize);
    this.geometry.setAttribute('aColor', this.aColor);
    this.geometry.setAttribute('aRot', this.aRot);
    this.geometry.setAttribute('aVel', this.aVel);
    this.geometry.instanceCount = 0;
    const material = new THREE.ShaderMaterial({
      uniforms: THREE.UniformsUtils.merge([
        THREE.UniformsLib.fog,
        { uMap: { value: map }, uStretch: { value: stretch }, uAdditive: { value: additive ? 1 : 0 } },
      ]),
      vertexShader: vertex,
      fragmentShader: fragment,
      transparent: true,
      depthWrite: false,
      blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
      fog: true,
    });
    material.uniforms.uMap.value = map;
    this.mesh = new THREE.Mesh(this.geometry, material);
    this.mesh.frustumCulled = false;
    this.mesh.renderOrder = additive ? 20 : 10;
    this.pos = new Float32Array(capacity * 3);
    this.vel = new Float32Array(capacity * 3);
    this.age = new Float32Array(capacity);
    this.life = new Float32Array(capacity);
    this.size0 = new Float32Array(capacity);
    this.size1 = new Float32Array(capacity);
    this.c0 = new Float32Array(capacity * 4);
    this.c1 = new Float32Array(capacity * 4);
    this.drag = new Float32Array(capacity);
    this.grav = new Float32Array(capacity);
    this.rot = new Float32Array(capacity);
    this.spin = new Float32Array(capacity);
  }

  get count() {
    return this.alive;
  }

  emit(p: EmitParams) {
    if (this.alive >= this.capacity) return;
    const i = this.alive++;
    const i3 = i * 3;
    const i4 = i * 4;
    this.pos[i3] = p.pos.x;
    this.pos[i3 + 1] = p.pos.y;
    this.pos[i3 + 2] = p.pos.z;
    this.vel[i3] = p.vel?.x ?? 0;
    this.vel[i3 + 1] = p.vel?.y ?? 0;
    this.vel[i3 + 2] = p.vel?.z ?? 0;
    this.age[i] = 0;
    this.life[i] = p.life;
    this.size0[i] = p.size;
    this.size1[i] = p.size1 ?? p.size;
    const c1 = p.color1 ?? p.color;
    this.c0[i4] = p.color.r;
    this.c0[i4 + 1] = p.color.g;
    this.c0[i4 + 2] = p.color.b;
    this.c0[i4 + 3] = p.alpha ?? 1;
    this.c1[i4] = c1.r;
    this.c1[i4 + 1] = c1.g;
    this.c1[i4 + 2] = c1.b;
    this.c1[i4 + 3] = p.alpha1 ?? 0;
    this.drag[i] = p.drag ?? 0;
    this.grav[i] = p.gravity ?? 0;
    this.rot[i] = p.rot ?? Math.random() * Math.PI * 2;
    this.spin[i] = p.spin ?? 0;
  }

  private kill(i: number) {
    const last = --this.alive;
    if (i === last) return;
    const copy = (arr: Float32Array, n: number) => {
      for (let k = 0; k < n; k++) arr[i * n + k] = arr[last * n + k];
    };
    copy(this.pos, 3);
    copy(this.vel, 3);
    copy(this.c0, 4);
    copy(this.c1, 4);
    this.age[i] = this.age[last];
    this.life[i] = this.life[last];
    this.size0[i] = this.size0[last];
    this.size1[i] = this.size1[last];
    this.drag[i] = this.drag[last];
    this.grav[i] = this.grav[last];
    this.rot[i] = this.rot[last];
    this.spin[i] = this.spin[last];
  }

  update(dt: number) {
    const off = this.aOffset.array as Float32Array;
    const size = this.aSize.array as Float32Array;
    const col = this.aColor.array as Float32Array;
    const rot = this.aRot.array as Float32Array;
    const vel = this.aVel.array as Float32Array;
    let i = 0;
    while (i < this.alive) {
      this.age[i] += dt;
      if (this.age[i] >= this.life[i]) {
        this.kill(i);
        continue;
      }
      const i3 = i * 3;
      const i4 = i * 4;
      const k = Math.exp(-this.drag[i] * dt);
      this.vel[i3] *= k;
      this.vel[i3 + 1] = this.vel[i3 + 1] * k - this.grav[i] * dt;
      this.vel[i3 + 2] *= k;
      this.pos[i3] += this.vel[i3] * dt;
      this.pos[i3 + 1] += this.vel[i3 + 1] * dt;
      this.pos[i3 + 2] += this.vel[i3 + 2] * dt;
      this.rot[i] += this.spin[i] * dt;
      const t = this.age[i] / this.life[i];
      const fadeIn = Math.min(1, t * 12);
      off[i3] = this.pos[i3];
      off[i3 + 1] = this.pos[i3 + 1];
      off[i3 + 2] = this.pos[i3 + 2];
      vel[i3] = this.vel[i3];
      vel[i3 + 1] = this.vel[i3 + 1];
      vel[i3 + 2] = this.vel[i3 + 2];
      size[i] = this.size0[i] + (this.size1[i] - this.size0[i]) * t;
      col[i4] = this.c0[i4] + (this.c1[i4] - this.c0[i4]) * t;
      col[i4 + 1] = this.c0[i4 + 1] + (this.c1[i4 + 1] - this.c0[i4 + 1]) * t;
      col[i4 + 2] = this.c0[i4 + 2] + (this.c1[i4 + 2] - this.c0[i4 + 2]) * t;
      col[i4 + 3] = (this.c0[i4 + 3] + (this.c1[i4 + 3] - this.c0[i4 + 3]) * t) * fadeIn;
      rot[i] = this.rot[i];
      i++;
    }
    this.geometry.instanceCount = this.alive;
    for (const a of [this.aOffset, this.aSize, this.aColor, this.aRot, this.aVel]) {
      a.clearUpdateRanges();
      a.addUpdateRange(0, Math.max(1, this.alive) * a.itemSize);
      a.needsUpdate = true;
    }
  }

  clear() {
    this.alive = 0;
    this.geometry.instanceCount = 0;
  }
}
