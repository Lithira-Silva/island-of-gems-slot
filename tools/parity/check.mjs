// Parity check: the JS MathEngine shipped in frontend/index.html must match math/engine.py exactly.
// Usage:  node tools/parity/check.mjs [tools/parity/fixtures.jsonl] [frontend/index.html]
// Exit code 1 on any mismatch. Python is the reference; fix the JS side unless the rule change is confirmed.
import { readFileSync, createReadStream } from 'node:fs';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const fixtures = process.argv[2] || path.join(root, 'tools/parity/fixtures.jsonl');
const html = readFileSync(process.argv[3] || path.join(root, 'frontend/index.html'), 'utf8').replace(/\r\n/g, '\n');

// Load exactly what ships: the injected config block and the MathEngine class source.
const CFG = JSON.parse(html.match(/<script id="game-config" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const NR = +html.match(/\bNR = (\d+)/)[1], NROW = +html.match(/\bNROW = (\d+)/)[1];
const src = html.match(/(class MathEngine \{[\s\S]*?\n\})\n/)[1];
const MathEngine = new Function('NR', 'NROW', `${src}; return MathEngine;`)(NR, NROW);
const eng = new MathEngine(CFG);

const EPS = 1e-9;
const close = (a, b) => Math.abs(a - b) <= EPS * Math.max(1, Math.abs(a), Math.abs(b));
// Deep compare; numbers within EPS. Returns the first differing path or null.
function diff(a, b, at = '') {
  if (typeof a === 'number' && typeof b === 'number') return close(a, b) ? null : at;
  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return `${at} (length ${a?.length} vs ${b?.length})`;
    for (let i = 0; i < a.length; i++) { const d = diff(a[i], b[i], `${at}[${i}]`); if (d) return d; }
    return null;
  }
  if (a && b && typeof a === 'object') {
    const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
    for (const k of keys) { const d = diff(a[k], b[k], `${at}.${k}`); if (d) return d; }
    return null;
  }
  return a === b ? null : at;
}
// Replays Python's recorded draws; JS must ask for the same range at every step, in the same order.
function replayRng(draws) {
  let i = 0;
  return {
    int(n) {
      if (i >= draws.length) throw new Error(`JS made draw #${i + 1} (range ${n}) but Python made only ${draws.length}`);
      const [pn, v] = draws[i++];
      if (pn !== n) throw new Error(`draw #${i}: JS asked for range ${n}, Python used ${pn}`);
      return v;
    },
    left: () => draws.length - i,
  };
}

const counts = {}, fails = [];
let total = 0;
const rl = createInterface({ input: createReadStream(fixtures), crlfDelay: Infinity });
for await (const line of rl) {
  if (!line) continue;
  const fx = JSON.parse(line), key = fx.kind === 'board' ? `board:${fx.src}` : `round:${fx.mode}`;
  counts[key] = (counts[key] || 0) + 1; total++;
  let d = null, got;
  try {
    if (fx.kind === 'board') {
      got = eng.evaluate(fx.board);
      d = diff({ wins: fx.wins, scatters: fx.scatters, total: fx.total }, got);
    } else {
      const rng = replayRng(fx.draws);
      got = eng.playRound(rng, fx.mode);
      d = diff({ payoutMultiplier: fx.payoutMultiplier, events: fx.events }, got) || (rng.left() ? `JS left ${rng.left()} draws unused` : null);
    }
  } catch (e) { d = `threw: ${e.message}`; }
  if (d) { fails.push({ key, at: d, fx, got }); if (fails.length >= 5) break; }
}

const summary = Object.entries(counts).map(([k, v]) => `${k}=${v}`).join('  ');
if (fails.length) {
  for (const f of fails) {
    console.error(`\nMISMATCH (${f.key}) at ${f.at}`);
    console.error('python:', JSON.stringify(f.fx.kind === 'board' ? { board: f.fx.board, wins: f.fx.wins, scatters: f.fx.scatters, total: f.fx.total } : { mode: f.fx.mode, payoutMultiplier: f.fx.payoutMultiplier, events: f.fx.events }).slice(0, 2000));
    console.error('js:    ', f.got === undefined ? '(no result: JS threw)' : JSON.stringify(f.got).slice(0, 2000));
  }
  console.error(`\nparity: FAIL (${fails.length}+ mismatches in ${total} fixtures checked)  ${summary}`);
  process.exit(1);
}
console.log(`parity: PASS, 0 mismatches in ${total} fixtures  ${summary}`);
