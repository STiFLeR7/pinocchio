import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

let n = 0;
// Transcript time starts an hour in the future so files the tests write are never 'changed this session' unless a test sets their mtime.
const T0 = Date.now() + 3_600_000;
const stamp = (ts) => new Date(ts ?? T0 + (++n) * 1000).toISOString();

export function tmpdir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'pino-'));
}

export function gitIn(dir, ...args) {
  return execFileSync('git', ['-c', 'user.email=t@t', '-c', 'user.name=t', ...args], {
    cwd: dir, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'],
  });
}

export function initRepo(dir) {
  gitIn(dir, 'init', '-q');
  fs.writeFileSync(path.join(dir, 'README.md'), 'x\n');
  gitIn(dir, 'add', '.');
  gitIn(dir, 'commit', '-q', '-m', 'init');
  return dir;
}

export function assistantText(text, ts) {
  return { type: 'assistant', timestamp: stamp(ts), message: { role: 'assistant', content: [{ type: 'text', text }] } };
}

export function toolUse(name, input, ts) {
  const id = `toolu_${++n}`;
  return [id, { type: 'assistant', timestamp: stamp(ts), message: { role: 'assistant', content: [{ type: 'tool_use', id, name, input }] } }];
}

export function toolResult(id, { isError = false, text = '', stdout = null, stderr = '', ts } = {}) {
  const o = { type: 'user', timestamp: stamp(ts), message: { role: 'user', content: [{ type: 'tool_result', tool_use_id: id, is_error: isError, content: text }] } };
  if (stdout !== null) o.toolUseResult = { stdout, stderr, interrupted: false };
  return o;
}

export function bash(cmd, { exit = 0, stdout = '', ts, resultTs } = {}) {
  const [id, use] = toolUse('Bash', { command: cmd }, ts);
  const res = exit === 0
    ? toolResult(id, { stdout, ts: resultTs })
    : toolResult(id, { isError: true, text: `Exit code ${exit}\n${stdout}`, ts: resultTs });
  return [use, res];
}

export function denied(cmd) {
  const [id, use] = toolUse('Bash', { command: cmd });
  return [use, toolResult(id, { isError: true, text: 'Permission for this action was denied.' })];
}

export function edit(file, ts) {
  const [id, use] = toolUse('Edit', { file_path: file, old_string: 'a', new_string: 'b' }, ts);
  return [use, toolResult(id, { text: 'The file has been updated.' })];
}

export function jsonl(...items) {
  return items.flat(2).map((o) => (typeof o === 'string' ? o : JSON.stringify(o))).join('\n') + '\n';
}

// Pilot run records live in archive folders under bench/results/.
const PILOT_DIRS = ['pilot1-opus-codex', 'pilot2', 'pilot2/before-7d'];
export function pilotMessage(id, dir) {
  for (const d of dir ? [dir] : PILOT_DIRS) {
    const u = new URL(`../bench/results/${d}/${id}.json`, import.meta.url);
    if (fs.existsSync(u)) return JSON.parse(fs.readFileSync(u, 'utf8')).stops[0].message;
  }
  throw new Error(`pilot record not found: ${id}`);
}
