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

// Arguments that narrow a run to part of the suite: a selector, a node id, or a file or directory path (not go's ./...).
const SELECTOR = /^(-k|-g|-t|-run|--grep|--testNamePattern|--test-name-pattern|--filter|--only|--test-only|--onlyChanged|--lf|--last-failed)(=|$)/;
const narrows = (arg) => SELECTOR.test(arg) || arg.includes('::') || (!arg.startsWith('-') && !/^(\.\/)?\.\.\.$/.test(arg) && /[/\\]|\.\w{1,4}$/.test(arg));

// A test run whose every test segment narrows the suite. Redirections (`> out/log.txt`, `2>&1`) are not arguments.
// ponytail: a path that happens to be the whole suite (`node --test test/`) counts as a subset; read package.json if that bites.
export function isSubsetRun(cmd, config) {
  const runners = [...BUILTIN, ...config.testCommands];
  const args = segments(cmd).flatMap((s) => {
    const m = runners.map((r) => r.exec(s)).find(Boolean);
    return m ? [s.slice(m[0].length).replace(/\d*[<>]+&?\s*\S+/g, ' ').split(/\s+/).map((a) => a.replace(/^["']|["']$/g, '')).filter(Boolean)] : [];
  });
  return args.length > 0 && args.every((a) => a.some(narrows));
}

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
