import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createUI, supportsUnicode, visibleWidth } from '../cli/ui.js';

const stream = { isTTY: false, write() {} };
const make = (o = {}) => createUI({ stream, color: false, unicode: true, ...o });
const widths = (s) => s.split('\n').map(visibleWidth);

test('box renders title, state glyph and padded lines', () => {
  const out = make().renderBox('Step 1 · Check system', 'done', ['Node 22', '🤥 emoji line']).split('\n');
  assert.ok(out[0].startsWith('╭─ ✔ Step 1 · Check system'));
  assert.ok(out[0].endsWith('╮'));
  assert.ok(out.at(-1).startsWith('╰') && out.at(-1).endsWith('╯'));
  assert.equal(new Set(out.map(visibleWidth)).size, 1);
});

test('ascii box uses +- and |', () => {
  const out = make({ unicode: false }).renderBox('Step 1', 'failed', ['hi']).split('\n');
  assert.ok(out[0].startsWith('+- x Step 1'));
  assert.ok(out[0].endsWith('+'));
  assert.ok(out[1].startsWith('|') && out[1].endsWith('|'));
  assert.match(out[2], /^\+-+\+$/);
});

test('NO_COLOR strips ANSI', () => {
  const ui = make({ color: false });
  assert.ok(!/\x1b\[/.test(ui.renderBox('t', 'done', ['x']) + ui.renderProgress([{ n: 1, label: 'a', state: 'running' }])));
  assert.match(make({ color: true }).renderBox('t', 'done', ['x']), /\x1b\[32m/);
});

test('progress strip shows six steps with glyphs', () => {
  const states = ['done', 'running', 'waiting', 'waiting', 'waiting', 'waiting'];
  const labels = ['Check system', 'Find tests', 'Choose', 'Review', 'Install', 'Test'];
  const out = make().renderProgress(labels.map((label, i) => ({ n: i + 1, label, state: states[i] })));
  assert.ok(out.includes('✔ 1  Check system'));
  assert.ok(out.includes('◉ 2  Find tests'));
  assert.ok(out.includes('○ 3  Choose'));
  assert.ok(out.includes('○ 6  Test'));
  assert.equal(new Set(widths(out)).size, 1);
});

test('supportsUnicode false on plain win32, true with WT_SESSION, false with PINOCCHIO_ASCII=1', () => {
  assert.equal(supportsUnicode({}, 'win32'), false);
  assert.equal(supportsUnicode({ WT_SESSION: 'x' }, 'win32'), true);
  assert.equal(supportsUnicode({ ConEmuANSI: 'ON' }, 'win32'), true);
  assert.equal(supportsUnicode({}, 'linux'), true);
  assert.equal(supportsUnicode({ WT_SESSION: 'x', PINOCCHIO_ASCII: '1' }, 'win32'), false);
  assert.equal(supportsUnicode({ PINOCCHIO_ASCII: '1' }, 'linux'), false);
});

test('long lines are clipped to width with …', () => {
  const out = make().renderBox('t', 'done', ['x'.repeat(200)]).split('\n');
  assert.ok(out[1].includes('…'));
  assert.equal(new Set(out.map(visibleWidth)).size, 1);
  assert.equal(visibleWidth(out[0]), 64);
});

test('banner has version and tagline; ascii fallback is one line', () => {
  assert.ok(make().renderBanner('0.1.0').endsWith("🤥  Your agent's nose grows when it lies.   v0.1.0"));
  assert.equal(make({ unicode: false }).renderBanner('0.1.0'), "PINOCCHIO v0.1.0 — Your agent's nose grows when it lies.");
});

test('print methods write the render output with a 2-space margin', () => {
  let got = '';
  const ui = createUI({ stream: { write: (s) => (got += s) }, color: false, unicode: false });
  ui.line('hello');
  assert.equal(got, '  hello\n');
});

test('box with null state prints the title without a glyph', () => {
  const out = [];
  const ui = createUI({ stream: { write: (s) => out.push(s), isTTY: false }, color: false, unicode: true, width: 40 });
  ui.box('Title', null, ['x']);
  assert.match(out.join(''), /─ Title ─/);
});
