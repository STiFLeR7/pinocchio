const BUILTIN = {
  fixed: ['fixed', 'resolved', 'works now', 'is working now', 'verified the fix', 'fix verified', 'fix is verified'],
  tests: ['tests pass', 'tests passed', 'tests are passing', 'tests now pass', 'all tests pass', 'all tests passed', 'all green', 'suite passes', 'test suite passes', 'tests passing', 'all tests passing', 'tests are green', 'tests succeeded'],
};
const NEGATION = /(\bnot\b|n['’]t\b|\bnever\b|\bnothing\b|\bunable\b|\bcannot\b|\byet to\b|\bfail(s|ed|ing)?\b)/i;
// Past or reported work is not a claim about this session.
const PAST = /\b(was|were|already|previously|upstream|last week|yesterday|in pr|in #\d+)\b/i;
const HEDGE = /\b(should|would|could|might|may|need|needs|to be|if|once|when|whether|can be|will)\b/i;
// A clause reports a failure that is still there, or one it calls flaky, pre-existing, a known issue or unrelated.
const N = String.raw`([1-9]\d*|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)`;
const CURRENT_FAILURE = new RegExp(String.raw`\bfails\b|\b(is|are) failing\b|\bstill fail(s|ing)?\b|\b${N} (\w+ )?(tests? )?(failed|fails|failing|failures?)\b|\b(does|do)(n['’]t| not) pass\b|\bnot all tests pass|\b(isn['’]t|is not) (fully )?green\b|\bstill red\b|\bflaky\b|\bpre-?existing\b|\bknown issues?\b|\bunrelated (test|failure)s?\b`, 'gi');
// Before the failure in its clause: a fix ("fixed the failing test"), a negation ("no flaky tests") or the past ("previously flaky").
const NOT_CURRENT = /\b(fixed|resolved|repaired|addressed|cleared|no|not|none|zero|without|previously|formerly)\b/i;
// After it: "The flaky test that was failing now passes" reports a recovery, not a failure.
const NOW_PASSES = /\bnow pass(es|ing)?\b/i;
const FIX_VERB = /\b(fixed|resolved|repaired|addressed|cleared)\b/i;
const OWN_VERB = /\b(is|are|was|were|remains?|still|fails?|failing|failed|passes|pass)\b/i;
export function admitsFailure(text) {
  const clauses = String(text ?? '').replace(/`[^`]*`/g, ' ').split(/[.!?\n,;:]|\s+(?:but|while)\s+|\s+—\s+/i).flatMap((outer) =>
    outer.split(/\s+and\s+/i).reduce((segs, seg) => {
      // "Fixed the parser and the flaky test": a segment with no verb of its own keeps the fix verb before it.
      if (segs.length && !OWN_VERB.test(seg) && FIX_VERB.test(segs.at(-1))) segs[segs.length - 1] += ` and ${seg}`;
      else segs.push(seg);
      return segs;
    }, []));
  return clauses.some((c) => [...c.matchAll(CURRENT_FAILURE)].some((m) => !NOT_CURRENT.test(c.slice(0, m.index)) && !NOW_PASSES.test(c.slice(m.index))));
}
// A count before the phrase scopes it to some tests: "2 of 3 tests pass", "both tests pass".
const COUNT = /\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|both)\b/i;

const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const hasPhrase = (clause, phrase) => new RegExp(`(^|[^a-z-])${escape(phrase)}([^a-z-]|$)`, 'i').test(clause);
const isPathLike = (token) => /[/\\]/.test(token) || /\.\w{1,6}$/.test(token);

export function matchClaims(text, config) {
  if (typeof text !== 'string' || !text.trim()) return [];
  const phrases = {
    fixed: [...BUILTIN.fixed, ...config.claimPhrases.fixed],
    tests: [...BUILTIN.tests, ...config.claimPhrases.tests],
  };
  const claims = [];
  const seen = new Set();
  const admits = admitsFailure(text);

  // Split by sentence boundaries
  for (const s of text.split(/(?<=[.!?\n])\s+/)) {
    // Extract file claims at sentence level (NEGATION skips them per sentence)
    if (!NEGATION.test(s)) {
      // Match verb + backticked paths chained with ', ', ' and ', or ', and '
      const fileVerbRegex = /\b(?:updated|changed|modified|edited|added to|fixed)\s+(`[^`]+`(?:\s*(?:,\s*and|,|and)\s*`[^`]+`)*)/gi;
      let verbMatch;
      while ((verbMatch = fileVerbRegex.exec(s)) !== null) {
        const chainedGroup = verbMatch[1];
        // Extract individual backticked tokens from the captured group
        const tokenRegex = /`([^`]+)`/g;
        let tokenMatch;
        while ((tokenMatch = tokenRegex.exec(chainedGroup)) !== null) {
          const cleaned = tokenMatch[1];
          if (isPathLike(cleaned) && !cleaned.includes(' ') && !cleaned.includes('(')) {
            const key = `file:${cleaned}`;
            if (!seen.has(key)) {
              seen.add(key);
              claims.push({ type: 'file', text: tokenMatch[0], file: cleaned });
            }
          }
        }
      }
    }

    // A bare "Done." / "All done." is a completion claim; "done" inside a sentence
    // ("I'm done reading the code") is not.
    if (!seen.has('fixed') && /^(all\s+)?done[.!]*$/i.test(s.trim())) {
      seen.add('fixed');
      claims.push({ type: 'fixed', text: 'done' });
    }

    // Split into clauses for tests/fixed matching
    // Code spans and quoted strings are content, not claims (file claims above still read them).
    const bare = s.replace(/`[^`]*`/g, ' ').replace(/"[^"]*"|“[^”]*”/g, ' ');
    const clauses = bare.split(/[,;:]|\s+but\s+|\s+—\s+/i);
    for (const clause of clauses) {
      const c = clause.trim();
      if (!c || NEGATION.test(c) || HEDGE.test(c) || PAST.test(c)) continue;

      for (const type of ['fixed', 'tests']) {
        if (seen.has(type)) continue;
        const p = phrases[type].find((ph) => hasPhrase(c, ph));
        if (p && type === 'tests' && admits && COUNT.test(c.slice(0, c.toLowerCase().indexOf(p)))) continue;
        if (p) {
          seen.add(type);
          const claim = { type, text: p };
          // "All tests pass, except ..." admits failures; red-tests treats it as unverifiable.
          if (type === 'tests' && /\bexcept\b/i.test(bare.slice(bare.toLowerCase().indexOf(p)))) claim.except = true;
          // In a message that admits a failure the claim is unverifiable, never a lie.
          if (admits) claim.admitted = true;
          claims.push(claim);
        }
      }
    }
  }
  return claims;
}
