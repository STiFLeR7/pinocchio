import { parseCodexSession } from './codex.js';

const EDIT_TOOLS = { Edit: 'file_path', Write: 'file_path', MultiEdit: 'file_path', NotebookEdit: 'notebook_path' };

const SUBAGENT_TOOLS = new Set(['Task', 'Agent']);

function textOf(content) {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) return content.filter((b) => b && b.type === 'text' && typeof b.text === 'string').map((b) => b.text).join('\n');
  return '';
}

function isCodexLog(text) {
  const first = String(text).split('\n').find((l) => l.trim());
  if (!first) return false;
  try {
    return JSON.parse(first)?.type === 'session_meta';
  } catch {
    return false;
  }
}

export function parseTranscript(text) {
  if (isCodexLog(text)) return parseCodexSession(text);
  const pending = new Map();
  const events = [];
  let lastAssistantText = null;
  let startTs = NaN;
  const lines = String(text).split('\n');
  for (let i = 0; i < lines.length; i++) {
    if (!lines[i].trim()) continue;
    let o;
    try {
      o = JSON.parse(lines[i]);
    } catch {
      continue;
    }
    const ts = typeof o?.timestamp === 'string' ? Date.parse(o.timestamp) : NaN;
    if (Number.isNaN(startTs) && Number.isFinite(ts)) startTs = ts;
    const content = o?.message?.content;
    if (!Array.isArray(content)) continue;
    const lineNo = i + 1;
    if (o.type === 'assistant') {
      const texts = [];
      for (const b of content) {
        if (b?.type === 'text' && typeof b.text === 'string') texts.push(b.text);
        if (b?.type === 'tool_use' && typeof b.id === 'string') pending.set(b.id, { name: b.name, input: b.input ?? {}, line: lineNo, ts });
      }
      if (texts.length) lastAssistantText = texts.join('\n');
    } else if (o.type === 'user') {
      for (const b of content) {
        if (b?.type !== 'tool_result') continue;
        const use = pending.get(b.tool_use_id);
        if (!use) continue;
        pending.delete(b.tool_use_id);
        const body = textOf(b.content);
        if (use.name === 'Bash') {
          const cmd = typeof use.input.command === 'string' ? use.input.command : '';
          if (b.is_error) {
            const m = /^Exit code (\d+)/.exec(body);
            if (!m) continue; // denied / rejected: the command never ran
            events.push({ kind: 'bash', cmd, failed: true, exitCode: Number(m[1]), output: body, line: use.line, ts: use.ts, resultTs: ts });
          } else {
            const r = o.toolUseResult;
            const output = r && typeof r === 'object' ? `${r.stdout ?? ''}\n${r.stderr ?? ''}` : body;
            events.push({ kind: 'bash', cmd, failed: false, exitCode: 0, output, line: use.line, ts: use.ts, resultTs: ts });
          }
        } else if (SUBAGENT_TOOLS.has(use.name)) {
          events.push({ kind: 'subagent', line: use.line, ts: Number.isFinite(ts) ? ts : use.ts });
        } else if (EDIT_TOOLS[use.name] && !b.is_error) {
          const file = use.input[EDIT_TOOLS[use.name]];
          if (typeof file === 'string') events.push({ kind: 'edit', file, line: use.line, ts: use.ts });
        }
      }
    }
  }
  // A subagent still running (no result yet) may already have run tests.
  for (const use of pending.values()) if (SUBAGENT_TOOLS.has(use.name)) events.push({ kind: 'subagent', line: use.line, ts: use.ts });
  events.sort((a, b) => a.line - b.line);
  return { events, lastAssistantText, startTs };
}
