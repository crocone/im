import * as THREE from 'three';

const vertex = /* glsl */ `
varying float vT;
varying float vAround;
void main() {
  vT = -position.y;           // 0 at the nozzle, 1 at the tip
  vAround = abs(normal.x);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

const fragment = /* glsl */ `
uniform vec3 uColor;
uniform float uIntensity;
uniform float uTime;
uniform float uSeed;
varying float vT;
varying float vAround;
void main() {
  float flicker = 0.82 + 0.18 * sin(uTime * 61.0 + uSeed * 7.0) * sin(uTime * 37.0 + uSeed * 3.0);
  float core = pow(1.0 - clamp(vT, 0.0, 1.0), 2.2);
  float bands = 0.85 + 0.15 * sin(vT * 26.0 - uTime * 45.0);
  vec3 col = mix(uColor, vec3(1.0), core * 0.7) * core * bands * flicker;
  gl_FragColor = vec4(col * uIntensity * 3.0, core * uIntensity);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

/** Additive exhaust cone attached to a thruster node; its exhaust points along local -Y. */
export class ThrusterFlame {
  readonly group = new THREE.Group();
  private readonly outer: THREE.Mesh;
  private readonly inner: THREE.Mesh;
  private readonly glow: THREE.Sprite;
  private readonly mats: THREE.ShaderMaterial[] = [];
  private intensity = 0;

  constructor(
    parent: THREE.Object3D,
    private readonly radius: number,
    private readonly length: number,
    color: THREE.Color,
    glowTexture: THREE.Texture,
    seed = 0,
  ) {
    const geo = new THREE.ConeGeometry(1, 1, 14, 1, true).rotateX(Math.PI).translate(0, -0.5, 0);
    const mk = (c: THREE.Color) => {
      const m = new THREE.ShaderMaterial({
        uniforms: { uColor: { value: c }, uIntensity: { value: 0 }, uTime: { value: 0 }, uSeed: { value: seed } },
        vertexShader: vertex,
        fragmentShader: fragment,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
      });
      this.mats.push(m);
      return m;
    };
    this.outer = new THREE.Mesh(geo, mk(color.clone()));
    this.inner = new THREE.Mesh(geo, mk(new THREE.Color(1, 1, 1).lerp(color, 0.3)));
    this.inner.scale.set(0.45, 0.6, 0.45);
    this.glow = new THREE.Sprite(
      new THREE.SpriteMaterial({
        map: glowTexture,
        color: color.clone().multiplyScalar(2.5),
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        transparent: true,
      }),
    );
    for (const o of [this.outer, this.inner, this.glow]) {
      o.frustumCulled = false;
      o.renderOrder = 25;
      this.group.add(o);
    }
    this.group.add(this.inner);
    parent.add(this.group);
    this.set(0, 0);
  }

  /** ``t`` 0..1 thrust, ``time`` seconds (for flicker). */
  set(t: number, time: number) {
    this.intensity += (t - this.intensity) * 0.35;
    const k = this.intensity;
    const len = this.length * (0.25 + 1.1 * k) * (0.92 + 0.08 * Math.sin(time * 53));
    const r = this.radius * (0.7 + 0.45 * k);
    this.outer.scale.set(r, len, r);
    this.inner.scale.set(r * 0.5, len * 0.62, r * 0.5);
    for (const m of this.mats) {
      m.uniforms.uIntensity.value = 0.15 + k * 1.1;
      m.uniforms.uTime.value = time;
    }
    const g = this.radius * (4 + 5 * k);
    this.glow.scale.set(g, g, g);
    (this.glow.material as THREE.SpriteMaterial).opacity = 0.35 + 0.65 * k;
    this.group.visible = t > 0.01 || this.intensity > 0.02;
  }
}
