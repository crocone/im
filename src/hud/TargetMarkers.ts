import * as THREE from 'three';

export interface MarkerInfo {
  position: THREE.Vector3;
  kind: 'enemy' | 'missile';
  label: string;
  /** bracket scale multiplier (boss) */
  scale: number;
}

interface Marker {
  root: HTMLDivElement;
  dist: HTMLDivElement;
  tag: HTMLDivElement;
  ring: SVGCircleElement;
  cls: string;
}

const RING_R = 30;
const RING_C = 2 * Math.PI * RING_R;
const _v = new THREE.Vector3();
const _fwd = new THREE.Vector3();

/** Screen-space target brackets, lock progress ring and edge-of-screen direction arrows. */
export class TargetMarkers {
  private readonly markers: Marker[] = [];
  private readonly arrows: HTMLDivElement[] = [];

  constructor(private readonly layer: HTMLElement) {}

  private marker(i: number): Marker {
    while (this.markers.length <= i) {
      const root = document.createElement('div');
      root.className = 'marker';
      root.innerHTML = `<div class="box"></div><div class="dist"></div><div class="tag"></div>
        <svg class="ring" viewBox="0 0 64 64"><circle cx="32" cy="32" r="${RING_R}" stroke-dasharray="${RING_C}" stroke-dashoffset="${RING_C}"/></svg>`;
      root.style.display = 'none';
      this.layer.appendChild(root);
      this.markers.push({
        root,
        dist: root.querySelector('.dist') as HTMLDivElement,
        tag: root.querySelector('.tag') as HTMLDivElement,
        ring: root.querySelector('circle') as SVGCircleElement,
        cls: '',
      });
    }
    return this.markers[i];
  }

  private arrow(i: number): HTMLDivElement {
    while (this.arrows.length <= i) {
      const a = document.createElement('div');
      a.className = 'offscreen';
      a.style.display = 'none';
      this.layer.appendChild(a);
      this.arrows.push(a);
    }
    return this.arrows[i];
  }

  update(
    camera: THREE.PerspectiveCamera,
    items: MarkerInfo[],
    current: MarkerInfo | null,
    progress: number,
    state: 'idle' | 'searching' | 'acquiring' | 'locked',
  ) {
    const w = window.innerWidth;
    const h = window.innerHeight;
    camera.getWorldDirection(_fwd);
    let mi = 0;
    let ai = 0;
    for (const it of items) {
      _v.subVectors(it.position, camera.position);
      const dist = _v.length();
      const inFront = _v.dot(_fwd) > 0;
      _v.copy(it.position).project(camera);
      const onScreen = inFront && Math.abs(_v.x) < 1 && Math.abs(_v.y) < 1;
      const isCurrent = it === current;
      if (onScreen) {
        const m = this.marker(mi++);
        const size = Math.max(24, Math.min(72, (1400 / Math.max(dist, 1)) * it.scale)) * (isCurrent ? 1.25 : 1);
        const cls = `marker ${it.kind}${isCurrent ? ' current' : ''}${isCurrent && state === 'locked' ? ' locked' : ''}`;
        if (m.cls !== cls) {
          m.root.className = cls;
          m.cls = cls;
        }
        m.root.style.display = 'block';
        m.root.style.left = `${((_v.x + 1) / 2) * w}px`;
        m.root.style.top = `${((1 - _v.y) / 2) * h}px`;
        m.root.style.width = m.root.style.height = `${size}px`;
        m.dist.textContent = `${Math.round(dist)} m`;
        m.tag.textContent = isCurrent ? (state === 'locked' ? 'LOCKED' : state === 'acquiring' ? 'ACQUIRING' : it.label) : it.kind === 'missile' ? 'MSL' : '';
        const p = isCurrent && (state === 'acquiring' || state === 'locked') ? (state === 'locked' ? 1 : progress) : 0;
        m.ring.setAttribute('stroke-dashoffset', `${RING_C * (1 - p)}`);
        m.ring.style.display = p > 0 ? 'block' : 'none';
      } else if (dist < 900) {
        // direction arrow on an ellipse around the screen centre
        let x = _v.x;
        let y = _v.y;
        if (!inFront) {
          x = -x;
          y = -y;
        }
        const ang = Math.atan2(y * h, x * w);
        const a = this.arrow(ai++);
        a.className = `offscreen ${it.kind === 'missile' ? 'missile' : ''}`;
        a.style.display = 'block';
        a.style.left = `${w / 2 + Math.cos(ang) * w * 0.42 - 9}px`;
        a.style.top = `${h / 2 - Math.sin(ang) * h * 0.4 - 9}px`;
        a.style.transform = `rotate(${Math.PI / 2 - ang}rad)`;
      }
    }
    for (let i = mi; i < this.markers.length; i++) this.markers[i].root.style.display = 'none';
    for (let i = ai; i < this.arrows.length; i++) this.arrows[i].style.display = 'none';
  }

  clear() {
    for (const m of this.markers) m.root.style.display = 'none';
    for (const a of this.arrows) a.style.display = 'none';
  }
}
