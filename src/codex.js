// Reads Codex CLI session logs (JSONL of { timestamp, type, payload }) into the same shape parseTranscript returns.
const SUBAGENT_ITEMS = new Set(['SubAgentActivity', 'CollabAgentToolCall']);

function agentText(item) {
  const c = item.content ?? item.text;
  if (typeof c === 'string') return c;
  if (Array.isArray(c)) return c.map((b) => (typeof b === 'string' ? b : b?.text)).filter((t) => typeof t === 'string').join('\n');
  return null;
}

export function parseCodexSession(text) {
  const events = [];
  let taskText = null;
  let messageText = null;
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
    if (Number.isNaN(startTs)) {
      const t = Date.parse(o?.type === 'session_meta' && o.payload?.timestamp ? o.payload.timestamp : o?.timestamp);
      if (Number.isFinite(t)) startTs = t;
    }
    const p = o?.payload;
    if (o?.type !== 'event_msg' || !p) continue;
    const line = i + 1;
    if (p.type === 'task_complete') {
      if (typeof p.last_agent_message === 'string') taskText = p.last_agent_message;
      continue;
    }
    const it = p.item;
    if (p.type !== 'item_completed' || !it) continue;
    if (it.type === 'CommandExecution') {
      if (it.status !== 'completed' && it.status !== 'failed') continue; // declined: the command never ran
      const cmd = Array.isArray(it.command) ? String(it.command.at(-1) ?? '') : String(it.command ?? '');
      events.push({ kind: 'bash', cmd, failed: it.exit_code !== 0, exitCode: it.exit_code, output: it.aggregated_output ?? '', line, ts: p.started_at_ms, resultTs: p.completed_at_ms });
    } else if (it.type === 'FileChange') {
      if (it.status !== 'completed') continue; // failed or still pending: nothing was written
      for (const file of Object.keys(it.changes ?? {})) events.push({ kind: 'edit', file, line, ts: p.completed_at_ms });
    } else if (SUBAGENT_ITEMS.has(it.type)) {
      events.push({ kind: 'subagent', line, ts: p.completed_at_ms });
    } else if (it.type === 'AgentMessage') {
      messageText = agentText(it) ?? messageText;
    }
  }
  return { events, lastAssistantText: taskText ?? messageText, startTs };
}
