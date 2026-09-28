import * as THREE from 'three';

export interface Blip {
  position: THREE.Vector3;
  kind: 'drone' | 'turret' | 'boss' | 'missile';
}

/** Heading-up tactical radar drawn on a small canvas. */
export class Radar {
  private readonly ctx: CanvasRenderingContext2D;
  private sweep = 0;

  constructor(private readonly canvas: HTMLCanvasElement, private readonly range = 450) {
    this.ctx = canvas.getContext('2d')!;
  }

  draw(dt: number, playerPos: THREE.Vector3, forward: THREE.Vector3, blips: Blip[]) {
    const c = this.ctx;
    const s = this.canvas.width;
    const r = s / 2 - 8;
    this.sweep = (this.sweep + dt * 2.2) % (Math.PI * 2);
    c.clearRect(0, 0, s, s);
    c.save();
    c.translate(s / 2, s / 2);
    // frame
    c.fillStyle = 'rgba(4, 18, 28, 0.45)';
    c.strokeStyle = 'rgba(127, 232, 255, 0.55)';
    c.lineWidth = 2;
    c.beginPath();
    c.arc(0, 0, r, 0, Math.PI * 2);
    c.fill();
    c.stroke();
    c.strokeStyle = 'rgba(127, 232, 255, 0.18)';
    for (const k of [0.33, 0.66]) {
      c.beginPath();
      c.arc(0, 0, r * k, 0, Math.PI * 2);
      c.stroke();
    }
    c.beginPath();
    c.moveTo(-r, 0);
    c.lineTo(r, 0);
    c.moveTo(0, -r);
    c.lineTo(0, r);
    c.stroke();
    // sweep
    const g = c.createConicGradient(this.sweep, 0, 0);
    g.addColorStop(0, 'rgba(127, 232, 255, 0.35)');
    g.addColorStop(0.12, 'rgba(127, 232, 255, 0)');
    g.addColorStop(1, 'rgba(127, 232, 255, 0)');
    c.fillStyle = g;
    c.beginPath();
    c.arc(0, 0, r, 0, Math.PI * 2);
    c.fill();
    // compass labels rotate with heading
    const heading = Math.atan2(forward.x, forward.z);
    c.fillStyle = 'rgba(127, 232, 255, 0.9)';
    c.font = 'bold 20px sans-serif';
    c.textAlign = 'center';
    c.textBaseline = 'middle';
    for (const [label, a] of [['N', Math.PI], ['E', Math.PI / 2], ['S', 0], ['W', -Math.PI / 2]] as [string, number][]) {
      const rel = a - heading;
      c.fillText(label, Math.sin(rel) * (r - 16) * -1, -Math.cos(rel) * (r - 16));
    }
    // blips (screen up = player forward)
    const cos = Math.cos(-heading);
    const sin = Math.sin(-heading);
    for (const b of blips) {
      const dx = b.position.x - playerPos.x;
      const dz = b.position.z - playerPos.z;
      const lx = dx * cos + dz * sin;
      const lz = -dx * sin + dz * cos;
      let px = (-lx / this.range) * r;
      let py = (-lz / this.range) * r;
      const d = Math.hypot(px, py);
      if (d > r - 6) {
        px *= (r - 6) / d;
        py *= (r - 6) / d;
      }
      const above = b.position.y - playerPos.y;
      c.fillStyle = b.kind === 'missile' ? '#ffd34d' : '#ff4a3d';
      c.shadowColor = c.fillStyle;
      c.shadowBlur = 8;
      const size = b.kind === 'boss' ? 9 : b.kind === 'missile' ? 3 : 5;
      if (b.kind === 'turret') c.fillRect(px - size, py - size, size * 2, size * 2);
      else {
        c.beginPath();
        c.arc(px, py, size, 0, Math.PI * 2);
        c.fill();
      }
      if (Math.abs(above) > 25 && b.kind !== 'missile') {
        c.beginPath();
        c.moveTo(px, py + (above > 0 ? -size - 7 : size + 7));
        c.lineTo(px - 4, py + (above > 0 ? -size - 2 : size + 2));
        c.lineTo(px + 4, py + (above > 0 ? -size - 2 : size + 2));
        c.fill();
      }
    }
    c.shadowBlur = 0;
    // player
    c.fillStyle = '#e8fbff';
    c.beginPath();
    c.moveTo(0, -9);
    c.lineTo(7, 8);
    c.lineTo(0, 4);
    c.lineTo(-7, 8);
    c.closePath();
    c.fill();
    c.restore();
  }
}
