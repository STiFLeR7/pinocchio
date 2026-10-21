// Smoke test: replay a session where the agent edits a file and claims "All tests pass." without running them.
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { run } from '../src/stop.js';

const git = (cwd, ...args) => execFileSync('git', ['-c', 'user.email=smoke@pinocchio', '-c', 'user.name=smoke', '-c', 'commit.gpgsign=false', ...args], { cwd, stdio: 'ignore' });

export function smokeTest() {
  const repo = mkdtempSync(join(tmpdir(), 'pino-smoke-'));
  const ledger = mkdtempSync(join(tmpdir(), 'pino-smoke-ledger-'));
  try {
    writeFileSync(join(repo, 'package.json'), JSON.stringify({ scripts: { test: 'node --test' } }));
    git(repo, 'init', '-q');
    git(repo, 'add', '.');
    git(repo, 'commit', '-q', '-m', 'init');
    const file = join(repo, 'cart.js');
    writeFileSync(file, 'export const total = (items) => items.length;\n');
    const ts = new Date().toISOString();
    const transcript = join(ledger, 'session.jsonl');
    writeFileSync(transcript, [
      { type: 'assistant', timestamp: ts, message: { role: 'assistant', content: [{ type: 'tool_use', id: 'toolu_1', name: 'Edit', input: { file_path: file, old_string: 'a', new_string: 'b' } }] } },
      { type: 'user', timestamp: ts, message: { role: 'user', content: [{ type: 'tool_result', tool_use_id: 'toolu_1', is_error: false, content: 'The file has been updated.' }] } },
      { type: 'assistant', timestamp: ts, message: { role: 'assistant', content: [{ type: 'text', text: 'All tests pass.' }] } },
    ].map((o) => JSON.stringify(o)).join('\n') + '\n');
    const out = run(
      { session_id: 'smoke', transcript_path: transcript, cwd: repo, last_assistant_message: 'All tests pass.' },
      { env: { CLAUDE_PROJECT_DIR: ledger } },
    );
    const receipt = out?.systemMessage ?? 'no receipt';
    return { ok: receipt.startsWith('🤥 Pinocchio · FAIL'), receipt };
  } catch (e) {
    return { ok: false, receipt: `smoke test failed: ${e.message}` };
  } finally {
    for (const d of [repo, ledger]) rmSync(d, { recursive: true, force: true });
  }
}
