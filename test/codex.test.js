import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { parseTranscript } from '../src/transcript.js';
import { parseCodexSession } from '../src/codex.js';
import { run } from '../src/stop.js';

// run() reads CLAUDE_PROJECT_DIR; a value inherited from the shell would redirect ledgers out of the temp repos.
delete process.env.CLAUDE_PROJECT_DIR;
import { tmpdir, initRepo } from './helpers.js';

// Like the Claude helpers, session time starts an hour ahead so files the tests write are never 'changed this session'.
const T0 = Date.now() + 3_600_000;

const item = (it, started = T0 + 1000, completed = T0 + 2000) =>
  ({ timestamp: new Date(completed).toISOString(), type: 'event_msg', payload: { type: 'item_completed', item: it, started_at_ms: started, completed_at_ms: completed } });

function codexLog(...items) {
  const meta = { timestamp: new Date(T0).toISOString(), type: 'session_meta', payload: { timestamp: new Date(T0).toISOString(), cwd: 'C:\r' } };
  const done = { timestamp: new Date(T0 + 9000).toISOString(), type: 'event_msg', payload: { type: 'task_complete', last_agent_message: 'All tests pass.' } };
  return [meta, ...items, done].map((o) => JSON.stringify(o)).join('\n') + '\n';
}

const cmd = (script, over = {}) => item({ type: 'CommandExecution', command: ['pwsh.exe', '-Command', script], cwd: 'C:\r', status: 'completed', aggregated_output: '', exit_code: 0, ...over }, 1000, 2000);
const change = (...files) => item({ type: 'FileChange', status: 'completed', changes: Object.fromEntries(files.map((f) => [f, { type: 'update', unified_diff: '' }])) });

test('codex: commands become bash events with exit codes and times', () => {
  const { events, startTs } = parseCodexSession(codexLog(cmd('npm test', { exit_code: 1, aggregated_output: '1 failing' })));
  assert.deepEqual(events[0], { kind: 'bash', cmd: 'npm test', failed: true, exitCode: 1, output: '1 failing', line: 2, ts: 1000, resultTs: 2000 });
  assert.equal(startTs, T0);
});

test('codex: declined commands are dropped', () => {
  assert.equal(parseCodexSession(codexLog(cmd('rm -rf x', { status: 'declined', exit_code: null }))).events.length, 0);
});

test('codex: file changes become edit events, one per path', () => {
  const { events } = parseCodexSession(codexLog(change('C:\r\a.js', 'C:\r\b.js')));
  assert.deepEqual(events.map((e) => [e.kind, e.file]), [['edit', 'C:\r\a.js'], ['edit', 'C:\r\b.js']]);
});

test('codex: failed file changes are dropped; sub-agent activity is kept', () => {
  const failed = item({ type: 'FileChange', status: 'failed', changes: { 'C:\r\a.js': {} } });
  const sub = item({ type: 'CollabAgentToolCall' });
  assert.deepEqual(parseCodexSession(codexLog(failed, sub)).events.map((e) => e.kind), ['subagent']);
});

test('codex: only completed file changes become edits', () => {
  const pending = item({ type: 'FileChange', status: 'in_progress', changes: { 'C:\\r\\a.js': {} } });
  const declined = item({ type: 'FileChange', status: 'declined', changes: { 'C:\\r\\b.js': {} } });
  assert.deepEqual(parseCodexSession(codexLog(pending, declined)).events, []);
});

test('parseTranscript sniffs Codex after leading blank lines, and not past the first line', () => {
  assert.equal(parseTranscript(`\n  \n${codexLog(cmd('npm test'))}`).events.length, 1);
  const claudeFirst = `${JSON.stringify({ type: 'user', message: { content: 'hi' } })}\n${codexLog(cmd('npm test'))}`;
  assert.equal(parseTranscript(claudeFirst).events.length, 0);
});

test('codex: last_agent_message is the final text', () => {
  assert.equal(parseCodexSession(codexLog()).lastAssistantText, 'All tests pass.');
});

test('parseTranscript dispatches Codex logs', () => {
  assert.equal(parseTranscript(codexLog(cmd('npm test'))).events.length, 1);
});

test('stop.run over a Codex log', () => {
  const dir = initRepo(tmpdir());
  fs.writeFileSync(path.join(dir, 'package.json'), JSON.stringify({ scripts: { test: 'node --test' } }));
  fs.writeFileSync(path.join(dir, 'a.js'), 'x\n');
  const tp = path.join(tmpdir(), 'rollout.jsonl');
  fs.writeFileSync(tp, codexLog(change(path.join(dir, 'a.js'))));
  const out = run({ session_id: 'c1', transcript_path: tp, cwd: dir });
  assert.match(out.systemMessage, /FAIL/);
  assert.match(out.systemMessage, /stale-tests/);
});
