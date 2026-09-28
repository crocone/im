import * as THREE from 'three';

interface Loop {
  src: AudioBufferSourceNode;
  filter: BiquadFilterNode;
  gain: GainNode;
}

const _d = new THREE.Vector3();

/** Fully synthesized WebAudio sound effects (no audio files) with distance attenuation and panning. */
export class AudioSystem {
  private ac: AudioContext | null = null;
  private master!: GainNode;
  private noiseBuf!: AudioBuffer;
  private thruster: Loop | null = null;
  private wind: Loop | null = null;
  private readonly listener = new THREE.Vector3();
  private readonly right = new THREE.Vector3(1, 0, 0);
  private shotBudget = 0;
  muted = false;

  /** Must be called from a user gesture (browser autoplay policy). */
  init() {
    if (this.ac) {
      void this.ac.resume();
      return;
    }
    const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AC) return;
    this.ac = new AC();
    const comp = this.ac.createDynamicsCompressor();
    comp.threshold.value = -14;
    comp.ratio.value = 6;
    this.master = this.ac.createGain();
    this.master.gain.value = 0.55;
    this.master.connect(comp).connect(this.ac.destination);
    this.noiseBuf = this.ac.createBuffer(1, this.ac.sampleRate * 2, this.ac.sampleRate);
    const data = this.noiseBuf.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
    this.thruster = this.loop('bandpass', 420, 0.8);
    this.wind = this.loop('lowpass', 300, 0.5);
  }

  private loop(type: BiquadFilterType, freq: number, q: number): Loop {
    const ac = this.ac!;
    const src = ac.createBufferSource();
    src.buffer = this.noiseBuf;
    src.loop = true;
    const filter = ac.createBiquadFilter();
    filter.type = type;
    filter.frequency.value = freq;
    filter.Q.value = q;
    const gain = ac.createGain();
    gain.gain.value = 0;
    src.connect(filter).connect(gain).connect(this.master);
    src.start();
    return { src, filter, gain };
  }

  toggleMute() {
    this.muted = !this.muted;
    if (this.ac) this.master.gain.setTargetAtTime(this.muted ? 0 : 0.55, this.ac.currentTime, 0.05);
    return this.muted;
  }

  suspend() {
    void this.ac?.suspend();
  }

  resume() {
    void this.ac?.resume();
  }

  setListener(pos: THREE.Vector3, right: THREE.Vector3) {
    this.listener.copy(pos);
    this.right.copy(right);
  }

  /** Continuous suit thrust + wind rush. */
  updateLoops(dt: number, thrust: number, boost: boolean, speedFactor: number, alive: boolean) {
    this.shotBudget = Math.min(8, this.shotBudget + dt * 18);
    if (!this.ac || !this.thruster || !this.wind) return;
    const t = this.ac.currentTime;
    const k = alive ? thrust : 0;
    this.thruster.gain.gain.setTargetAtTime(0.05 + k * 0.22 + (boost ? 0.18 : 0), t, 0.08);
    this.thruster.filter.frequency.setTargetAtTime(300 + k * 500 + (boost ? 700 : 0), t, 0.1);
    this.wind.gain.gain.setTargetAtTime(speedFactor * speedFactor * 0.5, t, 0.2);
    this.wind.filter.frequency.setTargetAtTime(200 + speedFactor * 1400, t, 0.2);
  }

  private spatial(pos?: THREE.Vector3): { gain: number; pan: number } {
    if (!pos) return { gain: 1, pan: 0 };
    _d.subVectors(pos, this.listener);
    const dist = _d.length();
    if (dist > 1100) return { gain: 0, pan: 0 };
    const pan = dist > 0.5 ? Math.max(-1, Math.min(1, _d.dot(this.right) / dist)) : 0;
    return { gain: 1 / Math.pow(1 + dist / 45, 1.3), pan };
  }

  private out(gainValue: number, pan: number, dur: number): GainNode | null {
    if (!this.ac || this.muted || gainValue < 0.003) return null;
    const g = this.ac.createGain();
    const p = this.ac.createStereoPanner();
    p.pan.value = pan;
    g.connect(p).connect(this.master);
    g.gain.value = gainValue;
    window.setTimeout(() => {
      g.disconnect();
      p.disconnect();
    }, (dur + 0.5) * 1000);
    return g;
  }

  private tone(type: OscillatorType, f1: number, f2: number, dur: number, vol: number, pos?: THREE.Vector3, delay = 0) {
    const s = this.spatial(pos);
    const g = this.out(vol * s.gain, s.pan, dur + delay);
    if (!g) return;
    const ac = this.ac!;
    const t = ac.currentTime + delay;
    const o = ac.createOscillator();
    o.type = type;
    o.frequency.setValueAtTime(f1, t);
    o.frequency.exponentialRampToValueAtTime(Math.max(1, f2), t + dur);
    const env = ac.createGain();
    env.gain.setValueAtTime(0.0001, t);
    env.gain.exponentialRampToValueAtTime(1, t + Math.min(0.012, dur / 4));
    env.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(env).connect(g);
    o.start(t);
    o.stop(t + dur + 0.05);
  }

  private noise(type: BiquadFilterType, f1: number, f2: number, dur: number, vol: number, pos?: THREE.Vector3, q = 1) {
    const s = this.spatial(pos);
    const g = this.out(vol * s.gain, s.pan, dur);
    if (!g) return;
    const ac = this.ac!;
    const t = ac.currentTime;
    const src = ac.createBufferSource();
    src.buffer = this.noiseBuf;
    src.playbackRate.value = 0.8 + Math.random() * 0.4;
    const f = ac.createBiquadFilter();
    f.type = type;
    f.Q.value = q;
    f.frequency.setValueAtTime(f1, t);
    f.frequency.exponentialRampToValueAtTime(Math.max(20, f2), t + dur);
    const env = ac.createGain();
    env.gain.setValueAtTime(1, t);
    env.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    src.connect(f).connect(env).connect(g);
    src.start(t, Math.random() * 1.5);
    src.stop(t + dur + 0.05);
  }

  repulsor() {
    this.tone('sawtooth', 1100, 160, 0.16, 0.16);
    this.tone('sine', 1800, 500, 0.12, 0.12);
    this.noise('highpass', 3000, 900, 0.1, 0.12);
  }

  missileLaunch() {
    this.noise('bandpass', 400, 2400, 0.9, 0.5, undefined, 0.7);
    this.tone('square', 90, 45, 0.25, 0.1);
  }

  miniLaunch() {
    this.noise('bandpass', 900, 3200, 0.4, 0.22, undefined, 1.2);
  }

  enemyMissile(pos: THREE.Vector3) {
    this.noise('bandpass', 350, 1800, 1.0, 0.5, pos, 0.8);
  }

  enemyShot(pos: THREE.Vector3, vol = 0.35) {
    if (this.shotBudget < 1) return;
    this.shotBudget -= 1;
    this.tone('square', 520, 120, 0.12, vol, pos);
  }

  explosion(pos: THREE.Vector3, scale: number) {
    const k = Math.min(2, 0.6 + scale * 0.4);
    this.noise('lowpass', 1400, 90, 0.8 + scale * 0.35, 1.1 * k, pos, 0.7);
    this.tone('sine', 85, 30, 0.6 + scale * 0.2, 0.9 * k, pos);
  }

  crumble(pos: THREE.Vector3) {
    this.noise('lowpass', 800, 60, 1.6, 0.9, pos, 0.5);
    this.noise('bandpass', 2400, 400, 0.6, 0.3, pos, 2);
  }

  shieldHit(explosive: boolean) {
    this.tone('sine', explosive ? 300 : 700, explosive ? 120 : 1400, 0.25, explosive ? 0.4 : 0.14);
  }

  shieldBreak() {
    this.tone('sawtooth', 900, 40, 1.4, 0.5);
    this.noise('highpass', 6000, 400, 1.2, 0.5);
  }

  beep(pitch: number) {
    this.tone('square', 700 + pitch * 700, 700 + pitch * 700, 0.05, 0.08);
  }

  lockTone() {
    this.tone('square', 1500, 1500, 0.09, 0.12);
    this.tone('square', 1500, 1500, 0.09, 0.12, undefined, 0.12);
    this.tone('square', 2000, 2000, 0.2, 0.12, undefined, 0.24);
  }

  dry() {
    this.tone('triangle', 220, 160, 0.08, 0.12);
  }

  playerHit() {
    this.noise('bandpass', 1800, 300, 0.25, 0.45, undefined, 1.5);
    this.tone('square', 160, 70, 0.18, 0.18);
  }

  thud(k: number) {
    this.tone('sine', 110, 40, 0.35, 0.5 * k);
    this.noise('lowpass', 900, 100, 0.3, 0.5 * k);
  }

  alarm() {
    for (let i = 0; i < 4; i++) this.tone('square', 880, 880, 0.14, 0.12, undefined, i * 0.3);
  }

  turretRise(pos: THREE.Vector3) {
    this.tone('sawtooth', 60, 140, 1.2, 0.3, pos);
  }

  turretWarn(pos: THREE.Vector3) {
    this.tone('square', 1200, 1200, 0.07, 0.3, pos);
    this.tone('square', 1200, 1200, 0.07, 0.3, pos, 0.12);
  }

  bossCharge() {
    this.tone('sawtooth', 60, 420, 1.3, 0.4);
  }

  bossDash() {
    this.noise('bandpass', 200, 1600, 1.0, 0.8, undefined, 0.6);
  }

  waveStart(boss: boolean) {
    const notes = boss ? [220, 207, 196, 185] : [330, 392, 494];
    notes.forEach((n, i) => this.tone(boss ? 'sawtooth' : 'triangle', n, n, 0.35, 0.18, undefined, i * 0.2));
  }

  waveClear() {
    [392, 494, 587, 784].forEach((n, i) => this.tone('triangle', n, n, 0.3, 0.16, undefined, i * 0.12));
  }

  stinger(win: boolean) {
    const notes = win ? [392, 494, 587, 784, 988] : [330, 262, 220, 165];
    notes.forEach((n, i) => this.tone('triangle', n, n, 0.5, 0.2, undefined, i * 0.22));
  }

  click() {
    this.tone('square', 1800, 1200, 0.04, 0.08);
  }
}
