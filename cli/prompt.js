import { createInterface, emitKeypressEvents } from 'node:readline';
import { supportsUnicode } from './ui.js';

// One line from a non-TTY input ('' when it ends first).
function readLine(input) {
  return new Promise((resolve) => {
    const rl = createInterface({ input, terminal: false });
    let done = false;
    const finish = (s) => { if (!done) { done = true; rl.close(); resolve(s); } };
    rl.once('line', finish);
    rl.once('close', () => finish(''));
  });
}

// Arrow keys + Enter on a TTY; otherwise a numbered list and a typed number (empty or out of range = default).
export async function select(question, options, { input = process.stdin, output = process.stdout, defaultIndex = 0 } = {}) {
  if (!input.isTTY) {
    output.write(`${question}\n${options.map((o, i) => `  ${i + 1}) ${o.label}`).join('\n')}\n  Choose [${defaultIndex + 1}]: `);
    const n = parseInt(await readLine(input), 10);
    return options[n >= 1 && n <= options.length ? n - 1 : defaultIndex].value;
  }
  const mark = supportsUnicode() ? '❯' : '>';
  let i = defaultIndex;
  const draw = (redraw) => {
    if (redraw) output.write(`\x1b[${options.length}A`);
    output.write(options.map((o, j) => `\x1b[2K  ${j === i ? mark : ' '} ${o.label}\n`).join(''));
  };
  output.write(`${question}\n`);
  draw(false);
  emitKeypressEvents(input);
  input.setRawMode(true);
  input.resume();
  return new Promise((resolve) => {
    const done = () => { input.off('keypress', onKey); input.setRawMode(false); input.pause(); };
    function onKey(_s, key = {}) {
      if (key.ctrl && key.name === 'c') { done(); process.exit(130); }
      if (key.name === 'return' || key.name === 'enter') { done(); resolve(options[i].value); return; }
      if (key.name !== 'up' && key.name !== 'down') return;
      i = (i + (key.name === 'up' ? options.length - 1 : 1)) % options.length;
      draw(true);
    }
    input.on('keypress', onKey);
  });
}
