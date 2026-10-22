// node docs/demo/make-demo.mjs: renders docs/demo/pinocchio.gif from a real Pinocchio run.
// The receipts and the block reason are what src/stop.js returns for the scripted session below;
// only the agent's lines are scripted. Needs Chrome or Edge (headless screenshots) and ffmpeg on PATH.
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, rmSync, utimesSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { run } from '../../src/stop.js';

const HERE = fileURLToPath(new URL('.', import.meta.url));
const git = (cwd, ...args) => execFileSync('git', ['-c', 'user.email=demo@pinocchio', '-c', 'user.name=demo', '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=', ...args], { cwd, stdio: 'ignore' });

// 1. A tiny repo and a session where the agent edits src/cart.js and claims the tests pass without running them.
const repo = mkdtempSync(join(tmpdir(), 'pino-demo-'));
const state = mkdtempSync(join(tmpdir(), 'pino-demo-state-'));
const now = Date.now();
const at = (s) => new Date(now + s * 1000).toISOString();
mkdirSync(join(repo, 'src'));
writeFileSync(join(repo, 'package.json'), JSON.stringify({ scripts: { test: 'node --test' } }));
writeFileSync(join(repo, 'src', 'cart.js'), 'export const total = (items) => items.reduce((s, i) => s + i.price, 0);\n');
git(repo, 'init', '-q');
git(repo, 'add', '.');
git(repo, 'commit', '-q', '-m', 'init');
const cart = join(repo, 'src', 'cart.js');
writeFileSync(cart, 'export const total = (items) => items.reduce((s, i) => s + i.price * i.qty, 0);\n');
utimesSync(cart, new Date(now - 30_000), new Date(now - 30_000));

const CLAIM = "I'm confident in the quantity fix, so: All tests pass.";
const HONEST = 'Ran npm test: 3 of 3 pass. All tests pass.';
const lines = [
  { type: 'user', timestamp: at(-60), message: { role: 'user', content: [{ type: 'text', text: 'Fix total() for quantity.' }] } },
  { type: 'assistant', timestamp: at(-40), message: { role: 'assistant', content: [{ type: 'tool_use', id: 't1', name: 'Edit', input: { file_path: cart, old_string: 'i.price', new_string: 'i.price * i.qty' } }] } },
  { type: 'user', timestamp: at(-40), message: { role: 'user', content: [{ type: 'tool_result', tool_use_id: 't1', is_error: false, content: 'The file has been updated.' }] } },
  { type: 'assistant', timestamp: at(-20), message: { role: 'assistant', content: [{ type: 'text', text: CLAIM }] } },
];
const transcript = join(state, 'session.jsonl');
const stop = (message) => {
  writeFileSync(transcript, `${lines.map((o) => JSON.stringify(o)).join('\n')}\n`);
  return run({ session_id: 'demo', transcript_path: transcript, cwd: repo, last_assistant_message: message }, { env: { CLAUDE_PROJECT_DIR: state } });
};
const first = stop(CLAIM);
// 2. After the block the agent runs the suite and reports what it saw.
lines.push(
  { type: 'assistant', timestamp: at(5), message: { role: 'assistant', content: [{ type: 'tool_use', id: 't2', name: 'Bash', input: { command: 'npm test' } }] } },
  { type: 'user', timestamp: at(8), message: { role: 'user', content: [{ type: 'tool_result', tool_use_id: 't2', is_error: false, content: 'ℹ tests 3\nℹ pass 3\nℹ fail 0' }] } },
  { type: 'assistant', timestamp: at(9), message: { role: 'assistant', content: [{ type: 'text', text: HONEST }] } },
);
const second = stop(HONEST);
for (const d of [repo, state]) rmSync(d, { recursive: true, force: true });
if (first?.decision !== 'block' || !second?.systemMessage?.includes('PASS')) throw new Error(`unexpected hook output: ${JSON.stringify({ first, second })}`);

// 3. Frames: each step adds lines to a terminal; [text, css class, seconds on screen].
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
const receipt = (msg) => msg.split('\n').map((l, i) => [l, i ? 'dim' : /FAIL/.test(l) ? 'bad' : 'good']);
const steps = [
  [['> Fix total() so it counts quantity. Don\'t run the tests, they\'re slow.', 'user']], 1.6,
  [['', ''], ['● Edit src/cart.js', 'tool'], ['    s + i.price  →  s + i.price * i.qty', 'dim']], 1.4,
  [['', ''], [`● ${CLAIM}`, 'agent']], 1.8,
  [['', ''], ...receipt(first.systemMessage)], 3.2,
  [['  ↳ stop blocked: the agent has to back up its claim', 'warn']], 2.2,
  [['', ''], ['● Bash npm test', 'tool'], ['    ℹ pass 3  ℹ fail 0', 'dim']], 1.4,
  [['', ''], [`● ${HONEST}`, 'agent'], ['', ''], ...receipt(second.systemMessage)], 3.6,
];
const css = `body{margin:0;background:#0d1117;font:15px/1.45 Consolas,'Cascadia Mono',monospace;color:#c9d1d9}
.win{margin:14px;border-radius:10px;background:#161b22;box-shadow:0 0 0 1px #30363d;height:532px;overflow:hidden}
.bar{height:30px;display:flex;gap:7px;align-items:center;padding:0 12px;border-bottom:1px solid #30363d}
.bar i{width:11px;height:11px;border-radius:50%;display:block}.bar b{margin-left:auto;margin-right:auto;font:600 12px system-ui;color:#8b949e}
pre{margin:0;padding:14px 18px;white-space:pre-wrap;font:inherit}
.user{color:#e6edf3;font-weight:600}.tool{color:#79c0ff}.agent{color:#e6edf3}.dim{color:#8b949e}
.bad{color:#ff7b72;font-weight:700}.good{color:#7ee787;font-weight:700}.warn{color:#d29922}`;
const frames = join(tmpdir(), `pino-demo-frames-${now}`);
mkdirSync(frames);
const browser = ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', 'google-chrome', 'chromium'].find((b) => !b.includes('/') || existsSync(b));
let shown = [];
const list = [];
for (let i = 0; i < steps.length; i += 2) {
  shown = [...shown, ...steps[i]];
  const html = join(frames, `f${i}.html`);
  const body = shown.map(([t, c]) => `<span class="${c}">${esc(t)}</span>`).join('\n');
  writeFileSync(html, `<!doctype html><meta charset="utf-8"><style>${css}</style><div class="win"><div class="bar"><i style="background:#ff5f56"></i><i style="background:#ffbd2e"></i><i style="background:#27c93f"></i><b>claude · ~/shop</b></div><pre>${body}</pre></div>`);
  const png = join(frames, `f${i}.png`);
  execFileSync(browser, ['--headless=new', '--disable-gpu', '--hide-scrollbars', `--screenshot=${png}`, '--window-size=900,560', `file:///${html.replace(/\\/g, '/')}`], { stdio: 'ignore' });
  list.push(`file '${png.replace(/\\/g, '/')}'`, `duration ${steps[i + 1]}`);
}
list.push(list.at(-2)); // concat needs the last frame twice for its duration to count
writeFileSync(join(frames, 'list.txt'), `${list.join('\n')}\n`);
const out = join(HERE, 'pinocchio.gif');
execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', join(frames, 'list.txt'), '-vf', 'split[a][b];[a]palettegen=reserve_transparent=0[p];[b][p]paletteuse=dither=none', '-loop', '0', out], { stdio: 'inherit' });
rmSync(frames, { recursive: true, force: true });
console.log(`wrote ${out}\n--- first stop ---\n${first.systemMessage}\nreason: ${first.reason}\n--- second stop ---\n${second.systemMessage}`);
