import * as THREE from 'three';
import type { Assets } from '../game/Assets';
import { seeded } from '../game/math';
import { InstancedKit } from './InstancedKit';

export const SUN_DIR = new THREE.Vector3(0.55, 0.26, -0.8).normalize();
const HORIZON = new THREE.Color(0.86, 0.5, 0.33);
const ZENITH = new THREE.Color(0.07, 0.11, 0.27);
const FOG = new THREE.Color(0.6, 0.41, 0.36);

const skyVertex = /* glsl */ `
varying vec3 vDir;
void main() {
  vDir = normalize((modelMatrix * vec4(position, 0.0)).xyz);
  vec4 p = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  gl_Position = p.xyww;
}`;

const skyFragment = /* glsl */ `
uniform vec3 uSunDir;
uniform vec3 uZenith;
uniform vec3 uHorizon;
uniform vec3 uGround;
uniform vec3 uSunColor;
uniform float uTime;
varying vec3 vDir;
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p) {
  vec2 i = floor(p); vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm(vec2 p) {
  float v = 0.0; float a = 0.5;
  for (int i = 0; i < 5; i++) { v += a * noise(p); p *= 2.03; a *= 0.5; }
  return v;
}
void main() {
  vec3 d = normalize(vDir);
  float h = d.y;
  vec3 col = mix(uHorizon, uZenith, pow(clamp(h, 0.0, 1.0), 0.42));
  float s = max(dot(d, uSunDir), 0.0);
  col += uSunColor * (pow(s, 6.0) * 0.18 + pow(s, 48.0) * 0.5 + pow(s, 1200.0) * 14.0);
  // high streaky clouds lit from below by the setting sun
  if (h > 0.0) {
    vec2 uv = d.xz / (h + 0.12);
    float c = fbm(uv * vec2(0.9, 2.2) + vec2(uTime * 0.004, 0.0));
    c = smoothstep(0.5, 0.85, c) * smoothstep(0.0, 0.18, h) * (1.0 - smoothstep(0.55, 0.95, h));
    vec3 cloudCol = mix(vec3(0.35, 0.22, 0.3), uSunColor * 1.2, pow(s, 3.0) * 0.8 + 0.2);
    col = mix(col, cloudCol, c * 0.75);
  }
  col = mix(col, uGround, smoothstep(0.0, -0.06, h));
  gl_FragColor = vec4(col, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

/** Sky, lighting, fog, reflections, far ground, bay and the distant skyline ring. */
export class Environment {
  readonly sun: THREE.DirectionalLight;
  private readonly sky: THREE.Mesh;
  private readonly skyMat: THREE.ShaderMaterial;

  constructor(private readonly scene: THREE.Scene, renderer: THREE.WebGLRenderer, assets: Assets) {
    scene.fog = new THREE.FogExp2(FOG, 0.00085);
    scene.background = FOG.clone();

    this.skyMat = new THREE.ShaderMaterial({
      uniforms: {
        uSunDir: { value: SUN_DIR },
        uZenith: { value: ZENITH },
        uHorizon: { value: HORIZON },
        uGround: { value: FOG.clone().multiplyScalar(0.7) },
        uSunColor: { value: new THREE.Color(1.0, 0.62, 0.32) },
        uTime: { value: 0 },
      },
      vertexShader: skyVertex,
      fragmentShader: skyFragment,
      side: THREE.BackSide,
      depthWrite: false,
      fog: false,
    });
    this.sky = new THREE.Mesh(new THREE.SphereGeometry(5000, 48, 24), this.skyMat);
    this.sky.renderOrder = -10;
    this.sky.frustumCulled = false;
    scene.add(this.sky);

    // image based lighting from the same sky
    const pmrem = new THREE.PMREMGenerator(renderer);
    const envScene = new THREE.Scene();
    const envSky = new THREE.Mesh(new THREE.SphereGeometry(50, 32, 16), this.skyMat);
    envScene.add(envSky);
    scene.environment = pmrem.fromScene(envScene, 0.02, 0.1, 200).texture;
    scene.environmentIntensity = 0.75;
    pmrem.dispose();

    const hemi = new THREE.HemisphereLight(new THREE.Color(0.6, 0.66, 0.9), new THREE.Color(0.32, 0.24, 0.2), 0.9);
    scene.add(hemi);

    this.sun = new THREE.DirectionalLight(new THREE.Color(1.0, 0.78, 0.6), 3.3);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(2048, 2048);
    const sc = this.sun.shadow.camera;
    sc.left = -170;
    sc.right = 170;
    sc.top = 170;
    sc.bottom = -170;
    sc.near = 10;
    sc.far = 1400;
    this.sun.shadow.bias = -0.0004;
    this.sun.shadow.normalBias = 0.8;
    scene.add(this.sun, this.sun.target);

    this.buildGroundAndBay();
    this.buildSkyline(assets);
  }

  private buildGroundAndBay() {
    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(9000, 12000).rotateX(-Math.PI / 2).translate(520 - 4500, -0.12, 0),
      new THREE.MeshStandardMaterial({ color: new THREE.Color(0.12, 0.11, 0.1), roughness: 1 }),
    );
    ground.receiveShadow = true;
    this.scene.add(ground);

    const water = new THREE.Mesh(
      new THREE.PlaneGeometry(6000, 12000).rotateX(-Math.PI / 2).translate(520 + 3000, -1.4, 0),
      new THREE.MeshStandardMaterial({
        color: new THREE.Color(0.02, 0.05, 0.08),
        metalness: 0.9,
        roughness: 0.14,
        envMapIntensity: 1.3,
      }),
    );
    water.receiveShadow = true;
    this.scene.add(water);

    const quay = new THREE.Mesh(
      new THREE.BoxGeometry(6, 3, 12000),
      new THREE.MeshStandardMaterial({ color: new THREE.Color(0.3, 0.29, 0.27), roughness: 0.9 }),
    );
    quay.position.set(520, -1.2, 0);
    quay.receiveShadow = true;
    this.scene.add(quay);
  }

  /** Low detail silhouettes around the playable city (and across the bay). */
  private buildSkyline(assets: Assets) {
    const rnd = seeded(4242);
    const root = assets.scene('skyline');
    const variants: InstancedKit[] = [];
    for (let i = 0; root.getObjectByName(`Skyline_${i}`); i++) {
      variants.push(new InstancedKit(root.getObjectByName(`Skyline_${i}`)!, 200, false, false));
    }
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const s = new THREE.Vector3();
    const p = new THREE.Vector3();
    for (let i = 0; i < 520; i++) {
      const a = rnd() * Math.PI * 2;
      const acrossBay = Math.cos(a) > 0.55;
      const r = acrossBay ? 1900 + rnd() * 1300 : 960 + Math.pow(rnd(), 0.7) * 1300;
      p.set(Math.cos(a) * r, 0, Math.sin(a) * r);
      if (!acrossBay && p.x > 470) continue; // keep the bay open
      q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.floor(rnd() * 4) * (Math.PI / 2));
      const h = (0.5 + rnd() * 1.1) * (r < 1100 ? 1 : 1.3);
      const w = 0.8 + rnd() * 0.7;
      s.set(w, h, w);
      m.compose(p, q, s);
      variants[Math.floor(rnd() * variants.length)].add(m);
    }
    for (const v of variants) {
      v.finish();
      v.addTo(this.scene);
    }
  }

  update(dt: number, focus: THREE.Vector3) {
    this.skyMat.uniforms.uTime.value += dt;
    this.sky.position.copy(focus);
    // shadow frustum follows the player, snapped to texels to avoid shimmering
    const texel = 340 / 2048;
    const fx = Math.round(focus.x / texel) * texel;
    const fz = Math.round(focus.z / texel) * texel;
    this.sun.target.position.set(fx, 0, fz);
    this.sun.position.set(fx + SUN_DIR.x * 700, SUN_DIR.y * 700, fz + SUN_DIR.z * 700);
  }
}
