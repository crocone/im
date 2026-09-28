import * as THREE from 'three';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';

/** WebGL renderer + HDR composer (MSAA render target, bloom, ACES tone mapping in OutputPass). */
export class GameRenderer {
  readonly renderer: THREE.WebGLRenderer;
  private readonly composer: EffectComposer;
  private readonly bloom: UnrealBloomPass;
  private frameTimes = 0;
  private frames = 0;
  private scale = 1;

  constructor(canvas: HTMLCanvasElement, scene: THREE.Scene, private readonly camera: THREE.PerspectiveCamera) {
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance', stencil: false });
    this.renderer.setPixelRatio(this.baseRatio());
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.0;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.info.autoReset = false;
    const size = this.size();
    const target = new THREE.WebGLRenderTarget(size.x, size.y, { type: THREE.HalfFloatType, samples: 4 });
    this.composer = new EffectComposer(this.renderer, target);
    this.composer.addPass(new RenderPass(scene, camera));
    this.bloom = new UnrealBloomPass(new THREE.Vector2(size.x / 2, size.y / 2), 0.5, 0.4, 1.8);
    this.composer.addPass(this.bloom);
    this.composer.addPass(new OutputPass());
    this.resize();
    window.addEventListener('resize', () => this.resize());
  }

  private baseRatio() {
    const q = new URLSearchParams(window.location.search).get('quality');
    const cap = q === 'low' ? 0.75 : q === 'high' ? 2 : 1.25;
    return Math.min(window.devicePixelRatio, cap) * this.scale;
  }

  /**
   * Dynamic resolution: if the average frame time stays above ~22 ms (under 45 fps) the render
   * scale drops in steps (down to 60 %), and creeps back up when there is headroom.
   */
  adapt(realDt: number) {
    this.frameTimes += realDt;
    this.frames++;
    if (this.frameTimes < 2) return;
    const avg = this.frameTimes / this.frames;
    this.frameTimes = 0;
    this.frames = 0;
    const prev = this.scale;
    if (avg > 0.022 && this.scale > 0.6) this.scale = Math.max(0.6, this.scale - 0.15);
    else if (avg < 0.0135 && this.scale < 1) this.scale = Math.min(1, this.scale + 0.1);
    if (prev !== this.scale) {
      this.renderer.setPixelRatio(this.baseRatio());
      this.resize();
    }
  }

  private size() {
    return new THREE.Vector2(window.innerWidth, window.innerHeight);
  }

  resize() {
    const s = this.size();
    this.renderer.setSize(s.x, s.y, false);
    this.composer.setPixelRatio(this.renderer.getPixelRatio());
    this.composer.setSize(s.x, s.y);
    this.camera.aspect = s.x / s.y;
    this.camera.updateProjectionMatrix();
  }

  render() {
    this.composer.render();
  }

  get info() {
    return this.renderer.info;
  }
}
