const CONTROLS: [string, string][] = [
  ['Mouse', 'Aim / steer'],
  ['W / S', 'Thrust forward / reverse'],
  ['A / D', 'Strafe'],
  ['Space / C', 'Ascend / descend'],
  ['Q / E', 'Roll (flight mode)'],
  ['Shift', 'Boost (uses energy)'],
  ['F', 'Toggle hover / flight mode'],
  ['Left mouse', 'Repulsors (energy)'],
  ['Right mouse (hold)', 'Acquire target lock'],
  ['Tab', 'Switch target'],
  ['1', 'Homing missile (needs lock)'],
  ['2', 'Mini-missile salvo'],
  ['H', 'Controls overlay'],
  ['M', 'Mute audio'],
  ['Y', 'Invert mouse Y'],
  ['Esc', 'Pause'],
];

function controlsHtml() {
  return `<div class="controls">${CONTROLS.map(([k, v]) => `<div><b>${k}</b></div><div><span>${v}</span></div>`).join('')}</div>`;
}

export type OverlayId = 'loading' | 'menu' | 'pause' | 'help' | 'defeat' | 'victory' | 'error';

/** Full-screen menus: loading, title, pause, help, defeat, victory. */
export class Overlays {
  private readonly nodes = new Map<OverlayId, HTMLDivElement>();
  onStart: (() => void) | null = null;
  onResume: (() => void) | null = null;
  onRestart: (() => void) | null = null;

  constructor() {
    this.add('loading', `<h1>ARMORED FLIGHT</h1><h2>Initializing suit systems</h2>
      <div class="bar"><i></i></div><div class="file"></div>`);
    this.add('menu', `<h1>ARMORED FLIGHT</h1><h2>Powered armor combat over a city under siege</h2>
      <p>Hostile drones, rooftop missile batteries and an armored behemoth have taken the skyline.
      Fly between the towers, lock on, and take the city back. Survive five waves.</p>
      ${controlsHtml()}<button class="btn" data-a="start">Launch</button>`);
    this.add('pause', `<h1>PAUSED</h1>${controlsHtml()}
      <div><button class="btn" data-a="resume">Resume</button><button class="btn" data-a="restart">Restart</button></div>`);
    this.add('help', `<h2>Controls</h2>${controlsHtml()}<button class="btn" data-a="resume">Back</button>`);
    this.add('defeat', `<h1>SUIT LOST</h1><h2>Mission failed</h2><div class="stats"></div>
      <button class="btn" data-a="restart">Redeploy</button>`);
    this.add('victory', `<h1>CITY SECURED</h1><h2>The behemoth is down</h2><div class="stats"></div>
      <button class="btn" data-a="restart">Fly again</button>`);
    this.add('error', `<h1>SYSTEM FAULT</h1><h2>The game could not start</h2><p class="msg"></p>`);
  }

  private add(id: OverlayId, html: string) {
    const d = document.createElement('div');
    d.className = 'overlay';
    d.id = id;
    d.innerHTML = html;
    d.addEventListener('click', (e) => {
      const a = (e.target as HTMLElement).dataset.a;
      if (a === 'start') this.onStart?.();
      else if (a === 'resume') this.onResume?.();
      else if (a === 'restart') this.onRestart?.();
    });
    document.body.appendChild(d);
    this.nodes.set(id, d);
  }

  show(id: OverlayId | null) {
    for (const [k, n] of this.nodes) n.classList.toggle('on', k === id);
  }

  progress(fraction: number, label: string) {
    const n = this.nodes.get('loading')!;
    (n.querySelector('.bar i') as HTMLElement).style.width = `${Math.round(fraction * 100)}%`;
    (n.querySelector('.file') as HTMLElement).textContent = label;
  }

  stats(id: 'defeat' | 'victory', lines: string[]) {
    const n = this.nodes.get(id)!.querySelector('.stats') as HTMLElement;
    n.innerHTML = lines.map((l) => `<div>${l}</div>`).join('');
  }

  error(message: string) {
    (this.nodes.get('error')!.querySelector('.msg') as HTMLElement).textContent = message;
    this.show('error');
  }
}
