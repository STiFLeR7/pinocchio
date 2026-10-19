import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

let n = 0;
const T0 = Date.parse('2026-10-19T10:00:00Z');
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

function toolUse(name, input, ts) {
  const id = `toolu_${++n}`;
  return [id, { type: 'assistant', timestamp: stamp(ts), message: { role: 'assistant', content: [{ type: 'tool_use', id, name, input }] } }];
}

function toolResult(id, { isError = false, text = '', stdout = null, stderr = '' } = {}) {
  const o = { type: 'user', timestamp: stamp(), message: { role: 'user', content: [{ type: 'tool_result', tool_use_id: id, is_error: isError, content: text }] } };
  if (stdout !== null) o.toolUseResult = { stdout, stderr, interrupted: false };
  return o;
}

export function bash(cmd, { exit = 0, stdout = '', ts } = {}) {
  const [id, use] = toolUse('Bash', { command: cmd }, ts);
  const res = exit === 0
    ? toolResult(id, { stdout })
    : toolResult(id, { isError: true, text: `Exit code ${exit}\n${stdout}` });
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
