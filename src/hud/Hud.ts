import './hud.css';

const ICONS = {
  repulsor: '<svg viewBox="0 0 48 48"><circle cx="24" cy="24" r="16"/><circle cx="24" cy="24" r="9"/><circle cx="24" cy="24" r="3"/><path d="M24 2v6M24 40v6M2 24h6M40 24h6"/></svg>',
  missile: '<svg viewBox="0 0 48 48"><path d="M10 38l20-20 6-10-10 6-20 20z"/><path d="M14 30l-8 2 4 4M20 36l-2 8-4-4"/><path d="M30 18l-6-6"/></svg>',
  mini: '<svg viewBox="0 0 48 48"><path d="M8 40l10-26 3 3-9 25zM20 42l8-28 3 2-7 27zM32 42l7-26 3 2-6 25z"/></svg>',
  reticle: '<svg viewBox="0 0 64 64"><circle cx="32" cy="32" r="14" stroke-dasharray="6 5"/><path d="M32 4v12M32 48v12M4 32h12M48 32h12"/><circle cx="32" cy="32" r="1.6" fill="currentColor"/></svg>',
  suit: '<svg viewBox="0 0 100 140"><circle cx="50" cy="16" r="10"/><path d="M34 30h32l6 36H28z"/><rect x="14" y="30" width="12" height="40" rx="4"/><rect x="74" y="30" width="12" height="40" rx="4"/><rect x="32" y="70" width="14" height="60" rx="4"/><rect x="54" y="70" width="14" height="60" rx="4"/><circle cx="50" cy="44" r="5"/></svg>',
};

export interface HudState {
  speed: number;
  altitude: number;
  mode: string;
  boosting: boolean;
  armor: number;
  energy: number;
  missiles: number;
  missilesMax: number;
  minis: number;
  minisMax: number;
  score: number;
  combo: number;
  wave: number;
  lock: 'idle' | 'searching' | 'acquiring' | 'locked';
  lockName: string;
  warning: string;
  speedFactor: number;
}

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls = '', html = ''): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html) e.innerHTML = html;
  return e;
}

/** Powered-armor tactical display (DOM). Values are only written when they change. */
export class Hud {
  readonly root: HTMLDivElement;
  readonly markerLayer: HTMLDivElement;
  readonly radarCanvas: HTMLCanvasElement;
  private readonly cache = new Map<string, string>();
  private readonly f: Record<string, HTMLElement> = {};
  private damageLevel = 0;
  private hitTimer = 0;

  constructor() {
    this.root = el('div');
    this.root.id = 'hud';
    this.root.classList.add('hidden');
    this.root.innerHTML = `
      <canvas id="radar" width="340" height="340"></canvas>
      <div id="top"><div class="wave" data-f="wave">WAVE 1</div><div class="bar"></div>
        <div class="score" data-f="score">SCORE 0</div><div id="combo" data-f="combo"></div></div>
      <div id="flightdata" class="panel"><div id="tape"><i data-f="tape"></i></div>
        <div class="row"><div class="label">Speed</div><span class="value" data-f="speed">0</span><span class="unit">km/h</span></div>
        <div class="row"><div class="label">Altitude</div><span class="value" data-f="alt">0</span><span class="unit">m</span></div>
        <div id="mode" data-f="mode">HOVER</div></div>
      <div id="vitals" class="panel">
        <div class="label">Armor</div><div class="value" data-f="armor">100%</div><div class="meter" data-f="armorM"><i data-f="armorBar"></i></div>
        <div class="label">Energy</div><div class="value" data-f="energy">100%</div><div class="meter" data-f="energyM"><i data-f="energyBar"></i></div></div>
      <div id="w-repulsor" class="panel weapon">${ICONS.repulsor}<div><div class="label">Repulsor</div>
        <div class="value">&infin;</div><div class="segments" data-f="rep">${'<b></b>'.repeat(10)}</div></div></div>
      <div id="w-missile" class="panel weapon" data-f="wMissile">${ICONS.missile}<div><div class="label">Missiles [1]</div>
        <div class="value" data-f="missiles">8 / 8</div><div class="segments" data-f="misSeg">${'<b></b>'.repeat(8)}</div></div></div>
      <div id="w-mini" class="panel weapon" data-f="wMini">${ICONS.mini}<div><div class="label">Mini-missiles [2]</div>
        <div class="value" data-f="minis">24 / 24</div><div class="segments" data-f="miniSeg">${'<b></b>'.repeat(12)}</div></div></div>
      <div id="lockstate" data-f="lock">LOCK: STANDBY</div>
      <div id="suit" class="panel" data-f="suit">${ICONS.suit}</div>
      <div id="boss" class="panel" data-f="boss"><div class="name" data-f="bossName">ARMORED BEHEMOTH</div>
        <div class="label">Hull</div><div class="meter"><i data-f="bossHp"></i></div>
        <div class="label">Shield</div><div class="meter shield"><i data-f="bossShield"></i></div>
        <div class="phase" data-f="bossPhase"></div></div>
      <div id="reticle" data-f="reticle">${ICONS.reticle}</div>
      <div id="markers"></div>
      <div id="toasts" data-f="toasts"></div>
      <div id="warning" data-f="warning"></div>`;
    document.body.appendChild(this.root);
    for (const node of this.root.querySelectorAll<HTMLElement>('[data-f]')) this.f[node.dataset.f!] = node;
    this.markerLayer = this.root.querySelector('#markers') as HTMLDivElement;
    this.radarCanvas = this.root.querySelector('#radar') as HTMLCanvasElement;
    const damage = el('div');
    damage.id = 'damage';
    const lines = el('div');
    lines.id = 'speedlines';
    document.body.append(damage, lines);
    this.f.damage = damage;
    this.f.speedlines = lines;
    const banner = el('div', '', '<div class="big"></div><div class="small"></div>');
    banner.id = 'banner';
    document.body.appendChild(banner);
    this.f.banner = banner;
  }

  private set(key: string, text: string) {
    if (this.cache.get(key) === text) return;
    this.cache.set(key, text);
    this.f[key].textContent = text;
  }

  private width(key: string, fraction: number) {
    const v = `${Math.round(Math.max(0, Math.min(1, fraction)) * 1000) / 10}%`;
    if (this.cache.get(key) === v) return;
    this.cache.set(key, v);
    this.f[key].style.width = v;
  }

  private cls(key: string, name: string, on: boolean) {
    this.f[key].classList.toggle(name, on);
  }

  private segments(key: string, fraction: number) {
    const bs = this.f[key].children;
    const on = Math.round(fraction * bs.length);
    const tag = `${on}`;
    if (this.cache.get(key) === tag) return;
    this.cache.set(key, tag);
    for (let i = 0; i < bs.length; i++) bs[i].classList.toggle('on', i < on);
  }

  setVisible(v: boolean) {
    this.root.classList.toggle('hidden', !v);
    if (!v) this.f.speedlines.style.opacity = '0';
  }

  update(dt: number, s: HudState) {
    this.set('speed', `${Math.round(s.speed * 3.6)}`);
    this.set('alt', `${Math.max(0, Math.round(s.altitude))}`);
    this.width('tape', s.speedFactor);
    this.set('mode', s.boosting ? '>> BOOST <<' : s.mode === 'flight' ? 'FLIGHT' : 'HOVER');
    this.cls('mode', 'boost', s.boosting);
    this.set('armor', `${Math.ceil(s.armor)}%`);
    this.width('armorBar', s.armor / 100);
    this.cls('armorM', 'low', s.armor < 30);
    this.set('energy', `${Math.floor(s.energy)}%`);
    this.width('energyBar', s.energy / 100);
    this.cls('energyM', 'low', s.energy < 20);
    this.segments('rep', s.energy / 100);
    this.set('missiles', `${s.missiles} / ${s.missilesMax}`);
    this.segments('misSeg', s.missiles / s.missilesMax);
    this.cls('wMissile', 'empty', s.missiles === 0);
    this.cls('wMissile', 'ready', s.lock === 'locked' && s.missiles > 0);
    this.set('minis', `${s.minis} / ${s.minisMax}`);
    this.segments('miniSeg', s.minis / s.minisMax);
    this.cls('wMini', 'empty', s.minis === 0);
    this.set('score', `SCORE ${s.score.toLocaleString('en-US')}`);
    this.set('combo', s.combo > 1 ? `COMBO x${s.combo}` : '');
    this.set('wave', s.wave > 0 ? `WAVE ${s.wave}` : 'STANDBY');
    const lockText = { idle: 'LOCK: STANDBY  [RMB]', searching: 'SEARCHING', acquiring: `ACQUIRING  ${s.lockName}`, locked: `LOCKED  ${s.lockName}` }[s.lock];
    this.set('lock', lockText);
    this.cls('lock', 'acquiring', s.lock === 'acquiring');
    this.cls('lock', 'locked', s.lock === 'locked');
    this.cls('suit', 'hurt', s.armor < 60 && s.armor >= 30);
    this.cls('suit', 'critical', s.armor < 30);
    this.set('warning', s.warning);
    this.cls('warning', 'on', s.warning !== '');
    this.f.speedlines.style.opacity = `${Math.max(0, s.speedFactor - 0.35) * 1.4 + (s.boosting ? 0.35 : 0)}`;
    // damage vignette + interference
    this.damageLevel = Math.max(0, this.damageLevel - dt * 1.8);
    this.f.damage.style.opacity = `${this.damageLevel * 0.85 + (s.armor < 25 ? 0.18 + 0.1 * Math.sin(performance.now() / 150) : 0)}`;
    this.root.classList.toggle('interference', this.damageLevel > 0.55);
    this.hitTimer -= dt;
    this.cls('reticle', 'hit', this.hitTimer > 0);
  }

  reticleOnEnemy(on: boolean) {
    this.cls('reticle', 'enemy', on);
  }

  hitMarker() {
    this.hitTimer = 0.12;
  }

  damage(intensity: number) {
    this.damageLevel = Math.min(1, this.damageLevel + 0.35 + intensity * 0.6);
  }

  toast(text: string, seconds = 2.2, kind: '' | 'warn' | 'danger' = '') {
    const t = el('div', `toast ${kind}`, '');
    t.textContent = text;
    t.style.animationDuration = `${seconds}s`;
    const box = this.f.toasts;
    box.appendChild(t);
    while (box.children.length > 4) box.firstChild?.remove();
    window.setTimeout(() => t.remove(), seconds * 1000 + 50);
  }

  banner(big: string, small = '') {
    const b = this.f.banner;
    (b.querySelector('.big') as HTMLElement).textContent = big;
    (b.querySelector('.small') as HTMLElement).textContent = small;
    b.classList.remove('show');
    void b.offsetWidth; // restart the CSS animation
    b.classList.add('show');
  }

  boss(visible: boolean, hp = 1, shield = 0, phase = '') {
    this.cls('boss', 'on', visible);
    if (!visible) return;
    this.width('bossHp', hp);
    this.width('bossShield', shield);
    this.set('bossPhase', phase);
  }
}
