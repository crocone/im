// Regenerates every GLB in public/assets with Blender, then verifies the result.
//
// Blender lookup order:
//   1. $BLENDER (path to the blender executable)
//   2. `blender` on PATH
//   3. common install locations (macOS / Windows / Linux)
//   4. a Python interpreter that can `import bpy` (the official `bpy` wheel from PyPI)
// The build aborts with a non-zero exit code if Blender is missing or any script fails.
import { spawnSync } from 'node:child_process';
import { existsSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const script = path.join(root, 'tools', 'blender', 'build_all.py');

function works(cmd, args) {
  try {
    const r = spawnSync(cmd, args, { encoding: 'utf8', timeout: 60000 });
    return r.status === 0;
  } catch {
    return false;
  }
}

function blenderCandidates() {
  const list = [];
  if (process.env.BLENDER) list.push(process.env.BLENDER);
  list.push('blender');
  list.push('/Applications/Blender.app/Contents/MacOS/Blender');
  list.push('/snap/bin/blender', '/usr/bin/blender', '/usr/local/bin/blender');
  const winRoot = 'C:\\Program Files\\Blender Foundation';
  if (existsSync(winRoot)) {
    for (const dir of readdirSync(winRoot).sort().reverse()) list.push(path.join(winRoot, dir, 'blender.exe'));
  }
  return list;
}

function run(cmd, args) {
  console.log(`[assets] ${cmd} ${args.join(' ')}`);
  const r = spawnSync(cmd, args, { cwd: root, stdio: 'inherit' });
  if (r.error) throw r.error;
  return r.status ?? 1;
}

let status = null;
const blender = blenderCandidates().find((c) => works(c, ['--version']));
if (blender) {
  status = run(blender, ['-b', '--factory-startup', '--python-exit-code', '1', '-P', script]);
} else {
  const python = ['python3', 'python'].find((p) => works(p, ['-c', 'import bpy']));
  if (python) {
    console.log('[assets] Blender executable not found; using the bpy Python module instead.');
    status = run(python, [script]);
  }
}

if (status === null) {
  console.error(
    '[assets] ERROR: Blender was not found. Install Blender 4.2+ and put it on PATH, set the BLENDER\n' +
      'environment variable to the executable, or `pip install bpy` for the headless Blender module.',
  );
  process.exit(1);
}
if (status !== 0) {
  console.error(`[assets] ERROR: Blender asset build failed (exit code ${status}).`);
  process.exit(status);
}
process.exit(run(process.execPath, [path.join(root, 'tools', 'verify-assets.mjs')]));
