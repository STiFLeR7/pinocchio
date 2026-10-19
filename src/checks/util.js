export function afterLastEdit(events) {
  let idx = -1;
  events.forEach((e, i) => {
    if (e.kind === 'edit') idx = i;
  });
  return { lastEdit: idx >= 0 ? events[idx] : null, after: events.slice(idx + 1) };
}

export function shortCmd(cmd) {
  const one = String(cmd).split('\n')[0].trim();
  return one.length > 60 ? `${one.slice(0, 57)}...` : one;
}
