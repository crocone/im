// Verifies that every required GLB exists, is a valid glTF 2.0 binary and contains the
// nodes / animations / colliders / debris chunks the game relies on. Exits non-zero on failure.
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const manifest = JSON.parse(readFileSync(path.join(root, 'src', 'assets.json'), 'utf8'));
const assetDir = path.join(root, 'public', 'assets');

function readGlb(file) {
  const buf = readFileSync(file);
  if (buf.length < 20 || buf.toString('ascii', 0, 4) !== 'glTF') throw new Error('not a GLB file');
  if (buf.readUInt32LE(4) !== 2) throw new Error('unsupported glTF version');
  const jsonLength = buf.readUInt32LE(12);
  if (buf.readUInt32LE(16) !== 0x4e4f534a) throw new Error('missing JSON chunk');
  return JSON.parse(buf.toString('utf8', 20, 20 + jsonLength));
}

const errors = [];
let totalBytes = 0;
for (const [key, spec] of Object.entries(manifest)) {
  const file = path.join(assetDir, spec.file);
  if (!existsSync(file)) {
    errors.push(`${spec.file}: missing (run \`npm run assets\`)`);
    continue;
  }
  totalBytes += readFileSync(file).length;
  let gltf;
  try {
    gltf = readGlb(file);
  } catch (e) {
    errors.push(`${spec.file}: ${e.message}`);
    continue;
  }
  const names = new Set((gltf.nodes ?? []).map((n) => n.name));
  for (const n of spec.nodes ?? []) if (!names.has(n)) errors.push(`${spec.file}: node "${n}" missing`);
  if (!gltf.meshes?.length) errors.push(`${spec.file}: contains no meshes`);
  if (spec.animations) {
    const clips = new Set((gltf.animations ?? []).map((a) => a.name.split('__')[0]));
    for (const a of spec.animations) if (!clips.has(a)) errors.push(`${spec.file}: pose "${a}" missing`);
  }
  if (spec.colliders && ![...names].some((n) => n.startsWith('COL_'))) errors.push(`${spec.file}: no COL_ colliders`);
  if (spec.minChunks) {
    const chunks = [...names].filter((n) => n.startsWith('chunk_')).length;
    if (chunks < spec.minChunks) errors.push(`${spec.file}: only ${chunks} debris chunks (need ${spec.minChunks})`);
  }
  if (!errors.some((e) => e.startsWith(spec.file))) console.log(`  ok  ${spec.file}  (${key})`);
}

if (errors.length) {
  console.error(`\n[verify-assets] ${errors.length} problem(s):`);
  for (const e of errors) console.error(`  - ${e}`);
  process.exit(1);
}
console.log(`[verify-assets] ${Object.keys(manifest).length} assets OK (${(totalBytes / 1048576).toFixed(1)} MB)`);
