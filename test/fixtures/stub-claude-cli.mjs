// Stand-in for `claude plugin ...`: logs argv (JSON line) to STUB_LOG, fails when argv[1] (or "marketplace <x>") equals STUB_FAIL.
import { appendFileSync } from 'node:fs';

const args = process.argv.slice(2);
if (process.env.STUB_LOG) appendFileSync(process.env.STUB_LOG, JSON.stringify(args) + '\n');
const sub = args[1] === 'marketplace' ? args[2] : args[1];
if (process.env.STUB_FAIL === sub) {
  process.stderr.write(`stub: ${sub} failed\n`);
  process.exit(1);
}
process.stdout.write(sub === 'list' ? '[{"id":"pinocchio@pinocchio","scope":"user"}]' : '{"ok":true}');
