import * as THREE from 'three';

const MAX_HITS = 6;

const vertex = /* glsl */ `
varying vec3 vNormalW;
varying vec3 vViewDir;
varying vec3 vLocal;
void main() {
  vLocal = normalize(position);
  vec4 world = modelMatrix * vec4(position, 1.0);
  vNormalW = normalize(mat3(modelMatrix) * normal);
  vViewDir = normalize(cameraPosition - world.xyz);
  gl_Position = projectionMatrix * viewMatrix * world;
}`;

const fragment = /* glsl */ `
#define MAX_HITS ${MAX_HITS}
uniform vec3 uColor;
uniform vec3 uHitColor;
uniform float uTime;
uniform float uStrength;   // 1 = full shield, 0 = depleted
uniform float uFlash;
uniform float uBreak;      // 0..1 dissolve after the shield collapses
uniform vec4 uHits[MAX_HITS]; // xyz = local impact direction, w = age (s), < 0 inactive
varying vec3 vNormalW;
varying vec3 vViewDir;
varying vec3 vLocal;

float hexGrid(vec3 p) {
  vec2 uv = vec2(atan(p.z, p.x) * 6.0, p.y * 9.0);
  vec2 r = vec2(1.0, 1.732);
  vec2 h = r * 0.5;
  vec2 a = mod(uv, r) - h;
  vec2 b = mod(uv - h, r) - h;
  vec2 g = dot(a, a) < dot(b, b) ? a : b;
  float edge = 0.5 - max(abs(g.x), dot(abs(g), normalize(vec2(1.0, 1.732))));
  return 1.0 - smoothstep(0.0, 0.06, edge);
}

float hash(vec3 p) { return fract(sin(dot(p, vec3(12.9898, 78.233, 37.719))) * 43758.5453); }

void main() {
  float fres = pow(1.0 - abs(dot(normalize(vNormalW), normalize(vViewDir))), 2.6);
  float grid = hexGrid(vLocal);
  float pulse = 0.55 + 0.45 * sin(uTime * 2.2 + vLocal.y * 5.0);
  float scan = smoothstep(0.96, 1.0, sin(vLocal.y * 12.0 - uTime * 3.0));
  float alpha = fres * 0.9 + grid * 0.16 * pulse + scan * 0.08;
  vec3 col = uColor * (0.7 + fres * 1.8 + grid * 0.8 * pulse);
  for (int i = 0; i < MAX_HITS; i++) {
    vec4 h = uHits[i];
    if (h.w < 0.0) continue;
    float d = acos(clamp(dot(vLocal, normalize(h.xyz)), -1.0, 1.0));
    float ring = exp(-pow((d - h.w * 2.4) * 9.0, 2.0)) * max(0.0, 1.0 - h.w * 1.6);
    float spot = exp(-d * d * 30.0) * max(0.0, 1.0 - h.w * 4.0);
    alpha += ring * 0.8 + spot * 1.2;
    col += uHitColor * (ring * 2.5 + spot * 4.0);
  }
  // weakened shields flicker and fray
  float noise = hash(floor(vLocal * 24.0) + floor(uTime * 12.0));
  float weak = 1.0 - uStrength;
  alpha *= 1.0 - weak * 0.5 * step(0.55, noise);
  col += uHitColor * uFlash * 1.5;
  alpha += uFlash * 0.35;
  // collapse: dissolve into drifting cells
  float cell = hash(floor(vLocal * 10.0));
  alpha *= 1.0 - smoothstep(cell - 0.1, cell, uBreak * 1.1);
  col += vec3(1.5, 1.8, 2.2) * uBreak * (1.0 - uBreak) * 4.0;
  gl_FragColor = vec4(col, clamp(alpha, 0.0, 1.0));
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

/** Energy shield: fresnel rim, hex lattice, impact ripples, weakened flicker and break dissolve. */
export class ShieldMaterial extends THREE.ShaderMaterial {
  private next = 0;

  constructor() {
    const hits = Array.from({ length: MAX_HITS }, () => new THREE.Vector4(0, 1, 0, -1));
    super({
      uniforms: {
        uColor: { value: new THREE.Color(0.25, 0.55, 1.4) },
        uHitColor: { value: new THREE.Color(0.7, 0.9, 1.6) },
        uTime: { value: 0 },
        uStrength: { value: 1 },
        uFlash: { value: 0 },
        uBreak: { value: 0 },
        uHits: { value: hits },
      },
      vertexShader: vertex,
      fragmentShader: fragment,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
  }

  /** Register an impact at a direction in the shield's local space. */
  impact(localDir: THREE.Vector3, flash = 1) {
    const hits = this.uniforms.uHits.value as THREE.Vector4[];
    hits[this.next].set(localDir.x, localDir.y, localDir.z, 0);
    this.next = (this.next + 1) % MAX_HITS;
    this.uniforms.uFlash.value = Math.max(this.uniforms.uFlash.value, flash);
  }

  tick(dt: number) {
    this.uniforms.uTime.value += dt;
    this.uniforms.uFlash.value = Math.max(0, this.uniforms.uFlash.value - dt * 3);
    for (const h of this.uniforms.uHits.value as THREE.Vector4[]) {
      if (h.w >= 0) {
        h.w += dt;
        if (h.w > 1.2) h.w = -1;
      }
    }
  }

  reset() {
    this.uniforms.uStrength.value = 1;
    this.uniforms.uBreak.value = 0;
    this.uniforms.uFlash.value = 0;
    for (const h of this.uniforms.uHits.value as THREE.Vector4[]) h.w = -1;
  }
}
