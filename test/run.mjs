import { readdirSync } from 'node:fs';
import { spawnSync } from 'node:child_process';

// Explicit file list: identical behaviour on Node 18/20/22 and never scans .venv/ or engine-room/.
const files = readdirSync(new URL('.', import.meta.url)).filter((f) => f.endsWith('.test.js')).sort().map((f) => `test/${f}`);
const r = spawnSync(process.execPath, ['--test', ...files], { stdio: 'inherit' });
process.exit(r.status ?? 1);
