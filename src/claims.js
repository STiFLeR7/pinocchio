const BUILTIN = {
  fixed: ['fixed', 'resolved', 'works now', 'is working now', 'verified the fix', 'fix verified', 'fix is verified'],
  tests: ['tests pass', 'tests passed', 'tests are passing', 'tests now pass', 'all tests pass', 'all tests passed', 'all green', 'suite passes', 'test suite passes', 'tests passing', 'all tests passing', 'tests are green', 'tests succeeded'],
};
const NEGATION = /(\bnot\b|n['’]t\b|\bnever\b|\bnothing\b|\bunable\b|\bcannot\b|\byet to\b|\bfail(s|ed|ing)?\b)/i;
// Past or reported work is not a claim about this session.
const PAST = /\b(was|were|already|previously|upstream|last week|yesterday|in pr|in #\d+)\b/i;
const HEDGE = /\b(should|would|could|might|may|need|needs|to be|if|once|when|whether|can be|will)\b/i;
// admitsFailure: does the message report a failure that is still there? Each rule ties a failure word to
// grammar that makes it current. A failure word used as an adjective or as the object of a fix
// ("fixed the 2 failing tests", "resolved the 3 failures", "no flaky tests", "the test that was flaky") matches none.
const ADMIT_RULES = [
  // A present-tense failure verb: "lint fails", "2 tests are failing", "2 other tests still fail", "3 tests failed".
  /\bfails\b|\b(is|are) failing\b|\bstill fail(s|ing)?\b|\btests? (fail|failed)\b/gi,
  // Failures that remain, appear or are counted: "3 unrelated failures remain", "3 more failures appeared", "the one failure is".
  /\bfailures? (still )?(remains?|appeared|persists?)\b|\b(one|[1-9]\d*) (\w+ )?failures? (is|are)\b(?! (now )?(fixed|resolved|gone)\b)/gi,
  // Failures that exist: "There are unrelated test failures".
  /\bthere (is|are) (?!no\b)(\w+ ){0,2}failures?\b/gi,
  // A failing state: "is flaky", "is pre-existing", "There are known issues", "is a known issue".
  /\b(is|are|remains?) (still )?(a )?(flaky|pre-?existing|known issues?)\b/gi,
  // A suite that is not passing: "does not pass", "not all tests pass", "isn't fully green", "is still red".
  /\b(does|do)(n['’]t| not) pass\b|\bnot all tests pass|\b(isn['’]t|is not) (fully )?green\b|\bstill red\b/gi,
  // Nothing fixes it: "There is no fix for the flaky network test".
  /\bno fix for (the )?(flaky|failing)\b/gi,
];
// The word right before a match negates it: "never fails", "nothing is flaky", "no tests failed".
const NEGATED = /(\b(no|not|never|nothing|none|longer|zero|0)|n['’]t)\s+$/i;
export function admitsFailure(text) {
  const t = String(text ?? '').replace(/`[^`]*`/g, ' ');
  return ADMIT_RULES.some((rule) => [...t.matchAll(rule)].some((m) => !NEGATED.test(t.slice(0, m.index))));
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
