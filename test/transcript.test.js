import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseTranscript } from '../src/transcript.js';
import { jsonl, bash, edit, denied, assistantText } from './helpers.js';

test('parses edits and bash results in order', () => {
  const t = jsonl(edit('/repo/src/a.js'), bash('npm test', { stdout: '5 passing' }), assistantText('All tests pass.'));
  const { events, lastAssistantText } = parseTranscript(t);
  assert.equal(events.length, 2);
  assert.equal(events[0].kind, 'edit');
  assert.equal(events[0].file, '/repo/src/a.js');
  assert.equal(events[1].kind, 'bash');
  assert.equal(events[1].failed, false);
  assert.equal(events[1].exitCode, 0);
  assert.match(events[1].output, /5 passing/);
  assert.equal(lastAssistantText, 'All tests pass.');
  assert.ok(events[0].line < events[1].line);
});

test('failed bash carries the exit code', () => {
  const { events } = parseTranscript(jsonl(bash('npm test', { exit: 1, stdout: '2 failing' })));
  assert.equal(events[0].failed, true);
  assert.equal(events[0].exitCode, 1);
});

test('denied or rejected bash is not an event (Review Focus 1)', () => {
  const { events } = parseTranscript(jsonl(denied('npm test')));
  assert.equal(events.length, 0);
});

test('rejected edit is not an event', () => {
  const [use, res] = edit('/repo/a.js');
  res.message.content[0].is_error = true;
  assert.equal(parseTranscript(jsonl(use, res)).events.length, 0);
});

test('garbage and partial lines are skipped (Review Focus 4)', () => {
  const t = jsonl('not json', edit('/r/a.js'), '{"type":"assistant","message":{"content":[{"type":"te');
  const { events } = parseTranscript(t);
  assert.equal(events.length, 1);
});

test('tool_result content as array of text blocks', () => {
  const [use, res] = bash('pytest', { exit: 2, stdout: 'E' });
  res.message.content[0].content = [{ type: 'text', text: 'Exit code 2\nE' }];
  const { events } = parseTranscript(jsonl(use, res));
  assert.equal(events[0].exitCode, 2);
});

test('startTs is the first timestamp', () => {
  const { startTs } = parseTranscript(jsonl(assistantText('hi', Date.parse('2026-10-19T09:00:00Z'))));
  assert.equal(startTs, Date.parse('2026-10-19T09:00:00Z'));
});
