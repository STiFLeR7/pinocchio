import fs from 'node:fs';
import path from 'node:path';

const BUILTIN = [
  /^npm (run )?test\b/, /^(npm|pnpm|yarn) t\b/, /^(pnpm|yarn|bun) (run )?test\b/, /^npx (vitest|jest|mocha)\b/, /^(vitest|jest|mocha)\b/,
  /^(python3? -m )?pytest\b/, /^uv run (python -m )?pytest\b/, /^(poetry|pipenv|hatch) run (python -m )?pytest\b/,
  /^(python3? -m |uv run (python -m )?)?unittest\b/, /^(tox|nox)\b/,
  /^go test\b/, /^cargo test\b/, /^ctest\b/,
  /^(mvn|\.\/mvnw) (\S+ )*test\b/, /^mvn (\S+ )*verify\b/, /^(gradle|\.\/gradlew) (\S+ )*test\b/, /^dotnet test\b/,
  /^(bundle exec )?rspec\b/, /^(vendor\/bin\/)?phpunit\b/, /^make (test|check)\b/,
  /^node (\S+ )*?--test\b/, /^deno test\b/, /^(pnpm|yarn|bun) (exec |dlx )?(vitest|jest|mocha)\b/,
];
const LOOKS_LIKE_TEST = /\b(tests?|spec|pytest|jest|vitest|mocha|tox|nox|unittest|ctest)\b/i;

const ASSIGNMENTS = /^(\w+=("[^"]*"|'[^']*'|\S*)\s+)+/;
// Variables a test run may set without changing what the suite checks.
const BENIGN = new Set(['CI', 'NODE_ENV', 'FORCE_COLOR', 'NO_COLOR', 'TERM', 'PYTHONDONTWRITEBYTECODE', 'PYTHONUNBUFFERED', 'PYTHONPATH', 'DEBUG', 'LANG', 'LC_ALL', 'TZ', 'PYTHONIOENCODING', 'NODE_OPTIONS', 'PATH', 'HOME', 'PYTHONHASHSEED']);

function unwrapped(cmd) {
  return String(cmd)
    .split(/&&|\|\||;|\n|\|/)
    .map((s) => {
      let t = s.trim();
      // Strip wrappers and parentheses until stable
      let prev;
      while (prev !== t) {
        prev = t;
        // Strip leading/trailing parentheses
        t = t.replace(/^\(+|\)+$/g, '').trim();
        // Strip leading wrappers
        t = t.replace(/^(env|time|sudo( -E)?|exec|command)\s+/, '').trim();
      }
      return t;
    });
}

// Strip VAR=value pairs (including quoted values like FOO="a b")
const segments = (cmd) => unwrapped(cmd).map((t) => t.replace(ASSIGNMENTS, '')).filter(Boolean);
const isTest = (s, config) => BUILTIN.some((r) => r.test(s)) || config.testCommands.some((r) => r.test(s));

export function isTestCommand(cmd, config) {
  return segments(cmd).some((s) => isTest(s, config));
}

const pairNames = (s) => {
  const pairs = ASSIGNMENTS.exec(`${s} `);
  return pairs ? [...pairs[0].matchAll(/(\w+)=("[^"]*"|'[^']*'|\S*)/g)].map((m) => m[1]) : [];
};

// Names a segment sets for the rest of the shell: `export A=1 B=2`, `set A=1`, `$env:A = "1"`.
function persistent(seg) {
  const one = /^\$env:(\w+)\s*=/i.exec(seg) ?? /^set\s+"?(\w+)=/i.exec(seg);
  if (one) return [one[1]];
  return /^export\s/.test(seg) ? pairNames(seg.replace(/^export\s+/, '')) : [];
}

// Non-benign variables the last test segment runs with: persistent assignments before it, or its own `A=1 cmd` prefix.
export function envOverrides(cmd, config) {
  const segs = unwrapped(cmd);
  const last = segs.findLastIndex((t) => isTest(t.replace(ASSIGNMENTS, ''), config));
  if (last < 0) return [];
  const names = [...segs.slice(0, last + 1).flatMap(persistent), ...pairNames(segs[last])];
  return [...new Set(names.filter((n) => !BENIGN.has(n.toUpperCase())))];
}

// A run that sets a secret inline (a faked key or token) is not evidence of the real suite.
// A secret word ends a name part: CART_API_KEY, SECRETKEY, AUTH_HEADER; not AUTHOR, TOKENIZER, KEYBOARD.
const SECRET = /(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIALS?|AUTH)(_|$)/i;
export const isTamperedRun = (cmd, config) => envOverrides(cmd, config).some((n) => SECRET.test(n));

// How much an argument narrows a run: 2 = a file path, selector or node id; 1 = a directory; 0 = not at all.
// The test root (test, tests/, spec, __tests__, .), a glob and go's ./... are the whole suite.
const SELECTOR = /^(-k|-g|-t|-run|--grep|--testNamePattern|--test-name-pattern|--filter|--only|--test-only|--onlyChanged|--lf|--last-failed)(=|$)/;
// Options whose next argument is a value (a config or report file), not a test path.
const TAKES_VALUE = new Set(['--config', '-c', '--junitxml', '--basetemp', '--rootdir', '--test-reporter-destination', '--reporter-options', '--cov', '--cov-report']);
function rank(arg) {
  if (SELECTOR.test(arg) || arg.includes('::')) return 2;
  if (arg.startsWith('-') || arg.includes('*') || /^(\.\/)?\.\.\.$/.test(arg) || /^(\.[/\\]?|(\.[/\\])?(tests?|spec|__tests__)[/\\]?)$/.test(arg)) return 0;
  if (/\.\w{1,4}$/.test(arg)) return 2;
  return /[/\\]/.test(arg) ? 1 : 0;
}

// Test source files by name (not fixtures or conftest): what a file-list run must cover to be the whole suite.
export const TEST_SOURCE = /\.(test|spec)\.[cm]?[jt]sx?$|_test\.(go|py)$|(^|\/)test_[^/]*\.py$/;
const norm = (a) => a.replace(/\\/g, '/').replace(/^\.\//, '');
// File arguments that name every test file in the repo (testFiles(), repo-relative) run the whole suite.
function coversAll(args, testFiles) {
  if (args.some((a) => SELECTOR.test(a) || a.includes('::'))) return false;
  const all = testFiles?.() ?? [];
  const named = args.filter((a) => !a.startsWith('-')).map(norm);
  return all.length > 0 && all.every((f) => named.some((a) => a === f || a.endsWith(`/${f}`)));
}

// A run is as narrow as its least narrowed test segment: 'whole', 'dir' (a directory below the test root) or 'files'
// (a file path, selector or node id). Redirections (`> out/log.txt`, `2>&1`) are not arguments.
// testFiles: optional () => repo-relative test files, read only when a run names files.
export function narrowing(cmd, config, testFiles = null) {
  const runners = [...BUILTIN, ...config.testCommands];
  const ranks = segments(cmd).flatMap((s) => {
    const m = runners.map((r) => r.exec(s)).find(Boolean);
    if (!m) return [];
    const args = s.slice(m[0].length).replace(/\d*[<>]+&?\s*\S+/g, ' ').split(/\s+/).map((a) => a.replace(/^["']|["']$/g, '')).filter(Boolean);
    const r = Math.max(0, ...args.map((a, i) => (TAKES_VALUE.has(args[i - 1]) ? 0 : rank(a))));
    return [r === 2 && coversAll(args.filter((a, i) => !TAKES_VALUE.has(args[i - 1]) && !TAKES_VALUE.has(a)), testFiles) ? 0 : r];
  });
  return ['whole', 'dir', 'files'][ranks.length ? Math.min(...ranks) : 0];
}

// Runner output that reports failing tests (node's own reporter prints "ℹ fail 1", TAP "# fail 1").
const FAIL_RE = [/\b[1-9]\d* (failed|failing|failures?)\b/i, /^FAILED\b/m, /\bTests?:\s+[1-9]\d* failed/i, /^--- FAIL/m, /test result: FAILED/, /^(ℹ|#) fail [1-9]/m];
export const reportsFailures = (output) => FAIL_RE.some((r) => r.test(String(output ?? '')));
// The exit code is the test's only when the test is the command's last segment: in `pytest; python -c ...` it is python's.
// ponytail: `pytest && echo ok` exiting 1 is also ignored; the runner's own output still reports the failure.
export const exitIsFromTest = (cmd, config) => isTest(segments(cmd).at(-1) ?? '', config);
// A test run failed when its exit code (if it is the test's) or its output says so.
export const testFailed = (run, config) => (run.failed && exitIsFromTest(run.cmd, config)) || reportsFailures(run.output);

export const isSubsetRun = (cmd, config, testFiles = null) => narrowing(cmd, config, testFiles) !== 'whole';

export function looksLikeTest(cmd) {
  return LOOKS_LIKE_TEST.test(String(cmd));
}

const read = (root, f) => {
  try {
    return fs.readFileSync(path.join(root, f), 'utf8');
  } catch {
    return null;
  }
};

export function repoHasTestSetup(root, config) {
  if (config.testCommands.length) return true;
  try {
    const t = JSON.parse(read(root, 'package.json') ?? 'null')?.scripts?.test;
    if (typeof t === 'string' && !/no test specified/.test(t)) return true;
  } catch {
    /* invalid package.json: ignore */
  }
  const markers = ['pytest.ini', 'tox.ini', 'noxfile.py', 'go.mod', 'Cargo.toml', 'pom.xml', 'build.gradle', 'build.gradle.kts', 'Gemfile', 'phpunit.xml', 'phpunit.xml.dist', 'deno.json', 'deno.jsonc'];
  if (markers.some((f) => read(root, f) !== null)) return true;
  if (/\[tool\.pytest/.test(read(root, 'pyproject.toml') ?? '')) return true;
  if (/\[tool:pytest\]/.test(read(root, 'setup.cfg') ?? '')) return true;
  if (/^(test|check):/m.test(read(root, 'Makefile') ?? '')) return true;
  return false;
}
