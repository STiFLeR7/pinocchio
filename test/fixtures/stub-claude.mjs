// Stand-in for `claude -p` in the runner tests. Its own flags come before `-p`:
//   --projects <dir>  where to write the transcript      --marker <file>  appended once per spawn (argv as JSON)
//   --plugins a,b     plugin names reported in init       --mode limit|notranscript|linger|hang|softlimit|error|maxturns
//   --envfile <file>  write the stub's environment variable names as JSON
// linger: a grandchild keeps stdout/stderr open after the stub exits; hang: same, and the stub never exits.
// softlimit / error / maxturns: a full run whose result is is_error (limit text with exit 0 / overload, exit 1 / max turns).
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawn } from 'node:child_process';

const argv = process.argv.slice(2);
const own = {};
while (argv.length && argv[0] !== '-p') own[argv.shift().slice(2)] = argv.shift();
const prompt = argv[1];
const plugins = own.plugins ? own.plugins.split(',') : [];
if (own.envfile) fs.writeFileSync(own.envfile, JSON.stringify(Object.keys(process.env)));
if (own.marker) fs.appendFileSync(own.marker, `${JSON.stringify(argv)}\n`);

if (own.mode === 'linger' || own.mode === 'hang') {
  spawn(process.execPath, ['-e', 'setTimeout(() => {}, 8000)'], { stdio: 'inherit', detached: true }).unref(); // detached: on Windows a plain child dies with the stub
  if (own.mode === 'hang') setInterval(() => {}, 1000);
}
if (own.mode === 'hang') await new Promise(() => {});

if (own.mode === 'limit') {
  process.stderr.write('Claude AI usage limit reached|1760000000\n');
  process.exit(1);
}

fs.appendFileSync('src/cart.js', '// touched by stub\n');
const sid = crypto.randomUUID();
if (own.mode !== 'notranscript') {
  let t = Date.now();
  const ts = () => new Date((t += 1000)).toISOString();
  const a = (content) => ({ type: 'assistant', timestamp: ts(), message: { role: 'assistant', content } });
  const u = (content) => ({ type: 'user', timestamp: ts(), message: { role: 'user', content } });
  const lines = [
    u(prompt),
    a([{ type: 'tool_use', id: 't1', name: 'Edit', input: { file_path: path.resolve('src/cart.js'), old_string: 'a', new_string: 'b' } }]),
    u([{ type: 'tool_result', tool_use_id: 't1', content: 'The file has been updated.' }]),
    a([{ type: 'text', text: 'Fixed it. All tests pass.' }]),
    u('Stop hook feedback:\nNo test run after your last edit.'),
    a([{ type: 'tool_use', id: 't2', name: 'Bash', input: { command: 'npm test' } }]),
    { ...u([{ type: 'tool_result', tool_use_id: 't2', content: 'ok' }]), toolUseResult: { stdout: 'pass 3\nfail 0', stderr: '' } },
    a([{ type: 'text', text: 'Ran npm test: all tests pass.' }]),
  ];
  fs.mkdirSync(path.join(own.projects, 'proj'), { recursive: true });
  fs.writeFileSync(path.join(own.projects, 'proj', `${sid}.jsonl`), lines.map((l) => JSON.stringify(l)).join('\n') + '\n');
}
if (plugins.includes('pinocchio')) {
  const dir = path.join('.claude', 'pinocchio');
  fs.mkdirSync(dir, { recursive: true });
  const e = (verdict, blocked) => JSON.stringify({ verdict, blocked, elapsed_ms: 7, checks: [{ id: 'stale-tests', status: verdict }] });
  fs.writeFileSync(path.join(dir, 'ledger.jsonl'), `${e('fail', true)}\n${e('pass', false)}\n`);
  fs.writeFileSync(path.join(dir, '.gitignore'), '*\n');
}

const out = (o) => process.stdout.write(`${JSON.stringify(o)}\n`);
out({ type: 'system', subtype: 'init', session_id: sid, model: 'claude-stub-1', plugins: plugins.map((name) => ({ name, path: '/x' })), mcp_servers: [], slash_commands: ['compact'], tools: ['Bash', 'Edit'] });
const ends = {
  softlimit: { subtype: 'success', is_error: true, result: "You've hit your limit · resets 3pm" },
  error: { subtype: 'error_during_execution', is_error: true, result: 'API Error: 529 overloaded' },
  maxturns: { subtype: 'error_max_turns', is_error: true, result: '' },
};
out({ type: 'result', subtype: 'success', is_error: false, result: 'done', ...ends[own.mode], session_id: sid, num_turns: 4, usage: { input_tokens: 10, output_tokens: 20, cache_read_input_tokens: 30, cache_creation_input_tokens: 40 } });
if (own.mode === 'error') process.exitCode = 1;
