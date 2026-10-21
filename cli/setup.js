// `pinocchio setup`: six step blocks; nothing is written before the Review step is confirmed.
import { cpSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, isAbsolute, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { createUI } from './ui.js';
import { checkSystem, detectTests } from './detect.js';
import { claudeCli } from './claude.js';
import { statePath, readState, writeState, sha256File } from './state.js';
import { hasHook, hookGroup, registerHook } from './fallback.js';
import { smokeTest } from './smoke.js';
import { select } from './prompt.js';

const PKG_ROOT = fileURLToPath(new URL('..', import.meta.url));
const VERSION = JSON.parse(readFileSync(join(PKG_ROOT, 'package.json'), 'utf8')).version;
const STEPS = ['Check system', 'Find tests', 'Choose', 'Review', 'Install', 'Test'];
const TITLES = ['Check system', 'Find your tests', 'Choose', 'Review — nothing written yet', 'Install', 'Test run'];
const RUNNERS = ['package.json', 'pyproject.toml', 'go.mod', 'Cargo.toml', 'Makefile'];
const SCOPES = [{ label: 'This project only', value: 'project' }, { label: 'All my projects', value: 'user' }];
const MODES = [
  { label: 'Default — block only when proven false', value: 'default' },
  { label: 'Report  — never block, just receipts', value: 'report' },
  { label: "Strict  — also block when it can't tell", value: 'strict' },
];
const YES_NO = [{ label: 'Yes', value: true }, { label: 'No', value: false }];
const NO_YES = [...YES_NO].reverse();
const FLAGS = { yes: { type: 'boolean' }, scope: { type: 'string' }, mode: { type: 'string' }, 'commit-ledger': { type: 'boolean' } };

const ver = (s) => s?.match(/\d+(\.\d+)+/)?.[0] ?? s;
const firstLine = (r) => (r.stderr || '').trim().split('\n')[0] || 'no details';
const labelOf = (list, v) => list.find((o) => o.value === v).label;
const inside = (base, p) => { const r = relative(base, p); return r && !r.startsWith('..') && !isAbsolute(r) ? r.replace(/\\/g, '/') : null; };

const pluginEntry = (cli) => {
  const r = cli.listPlugins();
  return (r.ok && Array.isArray(r.json) && r.json.find((p) => p?.id === 'pinocchio@pinocchio')) || null;
};
const hasMarketplace = (cli) => {
  const r = cli.listMarketplaces();
  return r.ok && Array.isArray(r.json) && r.json.some((m) => m?.name === 'pinocchio');
};

// State recorded and the registration it names still there (plugin listed and enabled, or the hook still in settings.json).
function installed(scopes, cwd, home, cli) {
  for (const scope of scopes) {
    const st = readState(statePath(scope, cwd, home));
    if (!st) continue;
    if (st.method === 'plugin') {
      const p = pluginEntry(cli);
      if (p && p.enabled !== false) return st;
    } else if (st.settings && hasHook(st.settings.file, st.settings.hookCommand)) return st;
  }
  return null;
}

export async function setup({
  cwd = process.cwd(), home = homedir(), argv = [], ui = createUI(),
  prompt = (question, options) => select(question, options), cli = claudeCli(),
  isTTY = Boolean(process.stdin.isTTY && process.stdout.isTTY), system,
} = {}) {
  let flags;
  try {
    flags = parseArgs({ args: argv, options: FLAGS }).values;
  } catch (e) {
    ui.line(`✖ ${e.message}`);
    return 1;
  }
  if (flags.scope && !SCOPES.some((s) => s.value === flags.scope)) { ui.line(`✖ --scope must be project or user (got "${flags.scope}")`); return 1; }
  if (flags.mode && !MODES.some((m) => m.value === flags.mode)) { ui.line(`✖ --mode must be default, report or strict (got "${flags.mode}")`); return 1; }
  const show = (p) => inside(cwd, p) ?? (inside(home, p) ? `~/${inside(home, p)}` : p);
  const box = (n, state, lines) => { ui.box(`Step ${n} · ${TITLES[n - 1]}`, state, lines); ui.line(''); };

  ui.banner(VERSION);
  ui.line('');
  const prev = installed(flags.scope ? [flags.scope] : ['project', 'user'], cwd, home, cli);
  ui.progress(STEPS.map((label, i) => ({ n: i + 1, label, state: prev ? 'done' : i === 0 ? 'running' : 'waiting' })));
  ui.line('');
  if (prev) {
    for (let n = 1; n <= 6; n++) box(n, 'done', ['✔ already set up']);
    ui.line(`Pinocchio is already set up (${prev.scope} scope, via ${prev.method === 'plugin' ? 'the plugin' : 'a settings.json hook'}). Nothing written.`);
    return 0;
  }

  // 1 · Check system
  const { node, git, claude, codex } = system ?? checkSystem();
  const sys = [[
    `${node.ok ? '✔' : '✖'} Node ${ver(node.version) ?? 'not found'}`,
    `${git.ok ? '✔' : '✖'} git ${ver(git.version) ?? 'not found'}`,
    claude.ok ? `✔ Claude Code ${ver(claude.version)}` : '─ Claude Code not found',
  ].join('      ')];
  if (codex.ok) sys.push(`● Codex ${ver(codex.version)}  → skill only (Codex has no blocking hook)`);
  if (!claude.ok) sys.push('  → Pinocchio will add a Stop hook to settings.json instead');
  if (!node.ok) sys.push('fix: install Node 18 or newer — https://nodejs.org');
  if (!git.ok) sys.push('fix: install git — https://git-scm.com');
  box(1, node.ok && git.ok ? 'done' : 'failed', sys);
  if (!node.ok || !git.ok) return 1;

  // 2 · Find tests
  const tests = detectTests(cwd);
  box(2, 'done', [
    `Looking in ${cwd} ...`,
    ...RUNNERS.map((f) => ` ${tests.some((t) => t.file === f) ? '✔' : '─'} ${f.padEnd(16)}→  ${tests.find((t) => t.file === f)?.command ?? 'not found'}`),
    tests.length ? 'Pinocchio will treat these as "real test runs".' : 'No runner found — Pinocchio will use its built-in list of test commands.',
  ]);

  // 3 · Choose
  const ask = isTTY && !flags.yes;
  const scope = flags.scope ?? (ask ? await prompt('Where to install?', SCOPES) : 'project');
  const mode = flags.mode ?? (ask ? await prompt('Mode?', MODES) : 'default');
  const commitLedger = flags['commit-ledger'] ?? (ask ? await prompt('Commit the lie ledger to git?', NO_YES) : false);
  box(3, 'done', [
    `Install for    ❯ ${labelOf(SCOPES, scope)}`,
    `Mode           ❯ ${labelOf(MODES, mode)}`,
    `Commit ledger  ❯ ${commitLedger ? 'yes' : 'no'}`,
  ]);

  // 4 · Review
  const scopeRoot = scope === 'user' ? home : cwd;
  const configFile = join(cwd, '.claude', 'pinocchio.json');
  const configExists = existsSync(configFile);
  const settingsFile = join(scopeRoot, '.claude', 'settings.json');
  const runtimeDir = join(scopeRoot, '.claude', 'pinocchio', 'runtime');
  const stateFile = statePath(scope, cwd, home);
  // The npx cache is temporary, so the hook runs a copy of the runtime; forward slashes work in bash and PowerShell.
  const hookCommand = `node "${runtimeDir.replace(/\\/g, '/')}/src/stop.js"`;
  // Read-only probes: Pinocchio may already be installed (natively, or by an earlier run whose state is gone).
  const plugin = claude.ok ? pluginEntry(cli) : null;
  const marketplace = Boolean(claude.ok && !plugin && hasMarketplace(cli));
  const hookLines = [`+ hook     Stop hook in ${show(settingsFile)}`, `+ folder   ${show(runtimeDir)}/   (runtime copy)`];
  box(4, 'running', [
    ...(plugin ? [` = plugin   pinocchio@pinocchio   (already installed${plugin.enabled === false ? ', disabled' : ''})`]
      : claude.ok ? [
        ` + plugin   pinocchio@pinocchio   (via claude plugin install)`,
        ...(marketplace ? [' = marketplace  pinocchio   (already added)'] : []),
        '   if the plugin install fails:', ...hookLines.map((l) => `     ${l}`),
      ]
      : hookLines.map((l) => ` ${l}`)),
    configExists ? ` = file     ${show(configFile)}   (exists, kept as is)` : ` + file     ${show(configFile)}   (your settings)`,
    ` + record   ${show(stateFile)}`,
    ` + folder   ${show(join(cwd, '.claude', 'pinocchio'))}/   (ledger, ${commitLedger ? 'committed' : 'ignored'})`,
    ' Token cost: ~93 tokens/session · 0 for the hook itself',
    ' Reads only: never edits code, never runs commands for you',
    ...(scope === 'user' ? [' Mode and ledger settings apply to this project; other projects use defaults.'] : []),
  ]);
  if (!flags.yes) {
    if (!isTTY) {
      ui.line('Nothing written. Not an interactive terminal — re-run with --yes to install.');
      return 1;
    }
    if (!(await prompt('Install now?', YES_NO))) {
      ui.line('Nothing written.');
      return 0;
    }
  }

  // 5 · Install
  const done = [];
  let method = 'settings';
  let reason = 'Claude Code CLI not found';
  // added* are true only for what this run added: uninstall removes exactly that.
  let addedMarketplace = false;
  let addedPlugin = false;
  if (plugin) {
    method = 'plugin';
    done.push('✔ already installed (pinocchio@pinocchio)');
    if (plugin.enabled === false) done.push('! the plugin is disabled — run: claude plugin enable pinocchio@pinocchio');
  } else if (claude.ok) {
    const add = marketplace ? { ok: true } : cli.marketplaceAdd(scope);
    if (!add.ok) reason = `claude plugin marketplace add failed: ${firstLine(add)}`;
    else {
      addedMarketplace = !marketplace;
      const inst = cli.install(scope);
      if (inst.ok) {
        method = 'plugin';
        addedPlugin = true;
        done.push(marketplace ? '✔ marketplace already added' : '✔ marketplace added', '✔ plugin installed');
      } else {
        if (addedMarketplace) cli.marketplaceRemove(scope); // leave nothing half-installed behind
        addedMarketplace = false;
        reason = `claude plugin install failed: ${firstLine(inst)}`;
      }
    }
  }
  let settings = null;
  let manual = false;
  if (method === 'settings') {
    done.push(`✖ ${reason}`, `→ using a Stop hook in ${show(settingsFile)} instead`);
    rmSync(runtimeDir, { recursive: true, force: true }); // no stale files from an older runtime
    cpSync(join(PKG_ROOT, 'src'), join(runtimeDir, 'src'), { recursive: true });
    cpSync(join(PKG_ROOT, 'package.json'), join(runtimeDir, 'package.json'));
    done.push(`✔ runtime copied to ${show(runtimeDir)}/`);
    settings = { file: settingsFile, hookCommand };
    const reg = registerHook(settingsFile, hookCommand);
    manual = !reg.ok;
    done.push(reg.ok ? '✔ Stop hook added' : `✖ ${show(settingsFile)} left untouched: ${reg.reason}`);
  }
  // A config recorded by an earlier setup stays recorded, so uninstall can still remove it.
  const files = configExists ? (readState(stateFile)?.files ?? []).filter((f) => f.path === configFile) : [];
  if (configExists) done.push(`✔ kept existing ${show(configFile)}`);
  else {
    mkdirSync(dirname(configFile), { recursive: true });
    writeFileSync(configFile, JSON.stringify({ mode, testCommands: tests.map((t) => t.regex), commitLedger }, null, 2) + '\n');
    files.push({ path: configFile, sha256: sha256File(configFile) });
    done.push('✔ settings saved');
  }
  writeState(stateFile, {
    version: 1, scope, method, addedMarketplace, addedPlugin, files, settings,
    runtime: method === 'settings' ? runtimeDir : null, at: new Date().toISOString(),
  });
  box(5, manual ? 'failed' : 'done', done);
  if (manual) {
    ui.line(`Add this to ${show(settingsFile)} by hand (merge with any "hooks" already there), then run: pinocchio doctor`);
    for (const l of JSON.stringify({ hooks: { Stop: [hookGroup(hookCommand)] } }, null, 2).split('\n')) ui.line(`  ${l}`);
    return 1;
  }

  // 6 · Test
  const smoke = smokeTest();
  box(6, smoke.ok ? 'done' : 'failed', [
    'Replaying a sample session where the agent lied...',
    ...smoke.receipt.split('\n').filter((l) => !/^\s*ledger /.test(l)).map((l) => ` ${l}`), // the sample's ledger is a temp dir
    smoke.ok ? '→ agent was sent back to run the tests' : '✖ expected a FAIL receipt — run: pinocchio doctor',
  ]);
  if (!smoke.ok) return 1;

  ui.line(' 🎉  Pinocchio is watching.  Restart Claude Code to begin.');
  ui.line(" pinocchio status     see your agent's nose count");
  ui.line(' pinocchio doctor     check everything is working');
  ui.line(' pinocchio uninstall  remove exactly what was added');
  return 0;
}
