import fs from 'node:fs';
import path from 'node:path';

const BUILTIN = [
  /^npm (run )?test\b/, /^(pnpm|yarn|bun) (run )?test\b/, /^npx (vitest|jest|mocha)\b/, /^(vitest|jest|mocha)\b/,
  /^(python3? -m )?pytest\b/, /^uv run (python -m )?pytest\b/, /^go test\b/, /^cargo test\b/,
  /^(mvn|\.\/mvnw) (\S+ )*test\b/, /^(gradle|\.\/gradlew) (\S+ )*test\b/, /^dotnet test\b/,
  /^(bundle exec )?rspec\b/, /^(vendor\/bin\/)?phpunit\b/, /^make (test|check)\b/,
];
const LOOKS_LIKE_TEST = /\b(tests?|spec|pytest|jest|vitest|mocha)\b/i;

function segments(cmd) {
  return String(cmd)
    .split(/&&|\|\||;|\n|\|/)
    .map((s) => s.trim().replace(/^(\w+=\S*\s+)+/, ''))
    .filter(Boolean);
}

export function isTestCommand(cmd, config) {
  return segments(cmd).some((s) => BUILTIN.some((r) => r.test(s)) || config.testCommands.some((r) => r.test(s)));
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
  const markers = ['pytest.ini', 'go.mod', 'Cargo.toml', 'pom.xml', 'build.gradle', 'build.gradle.kts', 'Gemfile', 'phpunit.xml', 'phpunit.xml.dist'];
  if (markers.some((f) => read(root, f) !== null)) return true;
  if (/\[tool\.pytest/.test(read(root, 'pyproject.toml') ?? '')) return true;
  if (/^(test|check):/m.test(read(root, 'Makefile') ?? '')) return true;
  return false;
}
