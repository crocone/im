/** Keyboard + mouse state with per-frame edge detection and pointer lock handling. */
export class Input {
  private readonly held = new Set<string>();
  private readonly pressed = new Set<string>();
  private readonly buttons = [false, false, false];
  private readonly clicked = [false, false, false];
  mouseDX = 0;
  mouseDY = 0;
  locked = false;
  invertY = false;
  onUnlock: (() => void) | null = null;

  constructor(private readonly target: HTMLElement) {
    window.addEventListener('keydown', (e) => {
      if (['Tab', 'Space', 'ArrowUp', 'ArrowDown', 'F1'].includes(e.code)) e.preventDefault();
      if (!this.held.has(e.code)) this.pressed.add(e.code);
      this.held.add(e.code);
    });
    window.addEventListener('keyup', (e) => this.held.delete(e.code));
    window.addEventListener('blur', () => {
      this.held.clear();
      this.buttons.fill(false);
    });
    target.addEventListener('mousedown', (e) => {
      if (e.button < 3) {
        this.buttons[e.button] = true;
        this.clicked[e.button] = true;
      }
    });
    window.addEventListener('mouseup', (e) => {
      if (e.button < 3) this.buttons[e.button] = false;
    });
    window.addEventListener('contextmenu', (e) => e.preventDefault());
    document.addEventListener('mousemove', (e) => {
      if (!this.locked) return;
      // Some browsers emit huge spikes when pointer lock engages; clamp them.
      this.mouseDX += Math.max(-250, Math.min(250, e.movementX));
      this.mouseDY += Math.max(-250, Math.min(250, e.movementY));
    });
    document.addEventListener('pointerlockchange', () => {
      const was = this.locked;
      this.locked = document.pointerLockElement === this.target;
      if (was && !this.locked) {
        this.held.clear();
        this.buttons.fill(false);
        this.onUnlock?.();
      }
    });
  }

  requestLock() {
    if (document.pointerLockElement === this.target) return;
    const p = this.target.requestPointerLock() as unknown as Promise<void> | undefined;
    if (p && typeof p.catch === 'function') p.catch(() => undefined);
  }

  releaseLock() {
    if (document.pointerLockElement) document.exitPointerLock();
  }

  down(code: string) {
    return this.held.has(code);
  }

  justPressed(code: string) {
    return this.pressed.has(code);
  }

  button(i: number) {
    return this.buttons[i];
  }

  buttonClicked(i: number) {
    return this.clicked[i];
  }

  axis(neg: string, pos: string) {
    return (this.held.has(pos) ? 1 : 0) - (this.held.has(neg) ? 1 : 0);
  }

  endFrame() {
    this.pressed.clear();
    this.clicked.fill(false);
    this.mouseDX = 0;
    this.mouseDY = 0;
  }
}
