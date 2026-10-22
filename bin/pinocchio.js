#!/usr/bin/env node
// `npx @stifler7/pinocchio <setup|doctor|status|uninstall> [flags]`
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const { version } = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'));
const USAGE = `pinocchio ${version}

Usage: pinocchio <command> [flags]

  setup      install Pinocchio (default)   --yes --scope project|user --mode default|report|strict --commit-ledger
  doctor     check the install
  status     show the nose count
  uninstall  remove exactly what setup added   --scope project|user
`;
const COMMANDS = {
  setup: async () => (await import('../cli/setup.js')).setup,
  doctor: async () => (await import('../cli/doctor.js')).doctor,
  status: async () => (await import('../cli/status.js')).status,
  uninstall: async () => (await import('../cli/uninstall.js')).uninstall,
};

const [first = 'setup', ...rest] = process.argv.slice(2);
if (first === '--version' || first === '-v') console.log(version);
else if (first === '--help' || first === '-h') process.stdout.write(USAGE);
else if (first.startsWith('-')) process.exitCode = (await run('setup', process.argv.slice(2)));
else if (COMMANDS[first]) process.exitCode = await run(first, rest);
else { process.stderr.write(`Unknown command: ${first}\n\n${USAGE}`); process.exitCode = 1; }

async function run(name, argv) {
  return (await (await COMMANDS[name]())({ argv })) ?? 0;
}
