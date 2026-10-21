// Terminal UI kit for the onboarding CLI: step-block boxes, progress strip, banner.
// render* functions return plain strings (no indent); the print twins write them with a 2-space margin.

const ANSI = /\x1b\[[0-9;]*m/g;
const LOGO = [
  '██████╗ ██╗███╗   ██╗ ██████╗  ██████╗ ██████╗██╗  ██╗██╗ ██████╗',
  '██╔══██╗██║████╗  ██║██╔═══██╗██╔════╝██╔════╝██║  ██║██║██╔═══██╗',
  '██████╔╝██║██╔██╗ ██║██║   ██║██║     ██║     ███████║██║██║   ██║',
  '██╔═══╝ ██║██║╚██╗██║██║   ██║██║     ██║     ██╔══██║██║██║   ██║',
  '██║     ██║██║ ╚████║╚██████╔╝╚██████╗╚██████╗██║  ██║██║╚██████╔╝',
  '╚═╝     ╚═╝╚═╝  ╚═══╝ ╚═════╝  ╚═════╝ ╚═════╝╚═╝  ╚═╝╚═╝ ╚═════╝',
];
const TAGLINE = "Your agent's nose grows when it lies.";
const COLORS = { done: 32, running: 33, failed: 31 };
const GLYPHS = {
  unicode: { done: '✔', running: '◉', waiting: '○', failed: '✖' },
  ascii: { done: 'v', running: '*', waiting: 'o', failed: 'x' },
};
const FRAMES = {
  round: { h: '─', v: '│', tl: '╭', tr: '╮', bl: '╰', br: '╯' },
  square: { h: '─', v: '│', tl: '┌', tr: '┐', bl: '└', br: '┘' },
  ascii: { h: '-', v: '|', tl: '+', tr: '+', bl: '+', br: '+' },
};

export function supportsUnicode(env = process.env, platform = process.platform) {
  if (env.PINOCCHIO_ASCII === '1') return false;
  if (platform !== 'win32') return true;
  return Boolean(env.WT_SESSION || env.TERM_PROGRAM || env.ConEmuANSI === 'ON');
}

// Terminal cells taken by one code point: emoji are 2 wide, joiners/variation selectors 0.
function cellWidth(ch) {
  const cp = ch.codePointAt(0);
  if (cp === 0x200d || (cp >= 0xfe00 && cp <= 0xfe0f)) return 0;
  return cp >= 0x1f300 ? 2 : 1;
}

export function visibleWidth(s) {
  let w = 0;
  for (const ch of s.replace(ANSI, '')) w += cellWidth(ch);
  return w;
}

// Clip to max cells, ending in … ; ANSI codes are kept (so colours still close) but cost nothing.
function clip(s, max) {
  if (visibleWidth(s) <= max) return s;
  let out = '';
  let w = 0;
  let cut = false;
  for (const part of s.split(/(\x1b\[[0-9;]*m)/)) {
    if (part.startsWith('\x1b')) { out += part; continue; }
    for (const ch of part) {
      const cw = cellWidth(ch);
      if (cut || w + cw > max - 1) { cut = true; continue; }
      out += ch;
      w += cw;
    }
  }
  return out + '…';
}

const pad = (s, w) => s + ' '.repeat(Math.max(0, w - visibleWidth(s)));

export function createUI({
  stream = process.stdout,
  color = !process.env.NO_COLOR && Boolean(stream.isTTY),
  unicode = supportsUnicode(),
  width = 64,
} = {}) {
  const glyphs = unicode ? GLYPHS.unicode : GLYPHS.ascii;
  const paint = (code, s) => (color && code ? `\x1b[${code}m${s}\x1b[0m` : s);
  const glyph = (state) => paint(COLORS[state], glyphs[state]);

  function frame(title, lines, shape = 'round') {
    const f = FRAMES[unicode ? shape : 'ascii'];
    const inner = width - 5; // │ + 2 spaces + text + space + │
    const t = clip(title, width - 6);
    const top = `${f.tl}${f.h} ${t} ${f.h.repeat(Math.max(1, width - visibleWidth(t) - 5))}${f.tr}`;
    const body = lines.map((l) => `${f.v}  ${pad(clip(l, inner), inner)} ${f.v}`);
    return [top, ...body, `${f.bl}${f.h.repeat(width - 2)}${f.br}`].join('\n');
  }

  const renderBox = (title, state, lines) => frame(`${glyph(state)} ${title}`, lines);

  function renderProgress(steps) {
    const cells = steps.map((s) => `${glyph(s.state)} ${s.n}  ${s.label}`);
    const rows = [];
    for (let i = 0; i < cells.length; i += 3) {
      rows.push(cells.slice(i, i + 3).map((c, j, row) => (j < row.length - 1 ? pad(c, 20) : c)).join('  '));
    }
    return frame('Setup', rows, 'square');
  }

  function renderBanner(version) {
    if (!unicode) return `PINOCCHIO v${version} — ${TAGLINE}`;
    return [...LOGO, `          🤥  ${TAGLINE}   v${version}`].join('\n');
  }

  const renderLine = (text) => text;

  const printer = (render) => (...args) => {
    const out = render(...args).split('\n').map((l) => (l ? `  ${l}` : l)).join('\n');
    stream.write(`${out}\n`);
  };

  return {
    renderBanner, renderProgress, renderBox, renderLine,
    banner: printer(renderBanner),
    progress: printer(renderProgress),
    box: printer(renderBox),
    line: printer(renderLine),
  };
}
