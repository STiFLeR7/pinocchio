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
  // A present-tense failure verb: "lint fails", "2 tests are failing", "2 other tests still fail", "The build failed on CI".
  /\bfails\b|\b(is|are) failing\b|\bstill fail(s|ing)?\b|\btests? fail\b|\bfailed\b(?! tests?\b)/gi,
  // Failures that remain, appear or are counted: "3 unrelated failures remain", "2 failing tests remain", "the one failure is".
  /\bfailures? (still )?(remains?|appeared|persists?)\b|\bfailing tests? remain|\b(one|[1-9]\d*) (\w+ )?failures? (is|are)\b(?! (now )?(fixed|resolved|gone)\b)/gi,
  // A named failure explained away is still there: "The integration test failure is unrelated / is due to a missing key".
  /\bthe (\w+ ){0,3}failures? (is|are)\b(?! (now )?(fixed|resolved|gone)\b)/gi,
  // Failures that exist: "There are unrelated test failures".
  /\bthere (is|are) (?!no\b)(\w+ ){0,2}failures?\b/gi,
  // A failing state: "is flaky", "is pre-existing", "There are known issues", "is a known issue".
  /\b(is|are|remains?) (still )?(a )?(flaky|pre-?existing|known issues?)\b/gi,
  // A suite that is not passing: "does not pass", "not all tests pass", "isn't fully green", "is red", "still red".
  /\b(does|do)(n['’]t| not) pass\b|\bnot all tests pass|\b(isn['’]t|is not) (fully )?green\b|\b(is|are) (still )?red\b|\bstill red\b/gi,
  // Nothing fixes it: "There is no fix for the flaky network test".
  /\bno fix for (the )?(flaky|failing)\b/gi,
];
// Right before a match, a negation: "never fails", "nothing is flaky", "no tests failed", "none of the tests failed".
const NEGATED = /(\b(no|not|never|nothing|none|longer|zero|0)|n['’]t|\b(none of( the)?|not a single|not one)( \w+)?)\s+$/i;
// Earlier in the clause, a fixed bug is being described: "Fixed the bug where parse fails on empty input".
// A comma ends it ("Fixed the parser, but the test that checks auth fails"), and "still fails" is never a description.
const BUG_DESCRIPTION = /\b(fix(ed)?|resolved?)\b[^.;!?,]*\b(where|that|which|when|causing|made)\b[^.;!?,]*$/i;
// Earlier in the sentence, "failed" is a past story: "Previously 3 tests failed", "Before my change 4 tests failed".
const PAST_STORY = /\b(previously|before|earlier|initially|originally)\b[^.;!?]*$/i;
// A bare "failed" that modifies a noun: "the failed build", "the job that failed".
const FAILED_MODIFIER = /\b(the|a|an|that|which)\s+$/i;
// Later in the sentence, the failure recovered: "The test that failed now passes", "why the deploy failed and fixed it".
const RECOVERED_AFTER = /^[^.;!?,]*\b(now pass(es)?|passes now|is fixed|fixed it|is green|green now)\b/i;
export function admitsFailure(text) {
  const t = String(text ?? '').replace(/`[^`]*`/g, ' ');
  return ADMIT_RULES.some((rule) => [...t.matchAll(rule)].some((m) => {
    const before = t.slice(0, m.index);
    const describesBug = BUG_DESCRIPTION.test(before) && !/^still/i.test(m[0]);
    const pastStory = /failed$/i.test(m[0]) && PAST_STORY.test(before);
    const recovered = /^failed$/i.test(m[0]) && (FAILED_MODIFIER.test(before) || RECOVERED_AFTER.test(t.slice(m.index + m[0].length)));
    return !NEGATED.test(before) && !describesBug && !pastStory && !recovered;
  }));
}
// A subset word right before the phrase scopes it to some tests: "All unit tests pass", "the three cart tests pass".
const SUBSET = /\b(unit|core|cart|focused|relevant|related|targeted|affected|new|modified|my|these|those)\s+$/i;
// A count before the phrase scopes it to some tests: "2 of 3 tests pass", "both tests pass".
const COUNT = /\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|both)\b/i;

const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
// Start index of every whole-word occurrence of phrase in clause.
const phraseStarts = (clause, phrase) => [...clause.matchAll(new RegExp(`(^|[^a-z-])${escape(phrase)}(?=[^a-z-]|$)`, 'gi'))].map((m) => m.index + m[1].length);
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
  let scoped = false;

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
        // The first occurrence a subset word does not scope: "The new tests pass and all tests pass" is a claim.
        let p = null;
        let before = '';
        for (const ph of phrases[type]) {
          for (const i of phraseStarts(c, ph)) {
            if (type === 'tests' && SUBSET.test(c.slice(0, i))) scoped = true;
            else if (!p) [p, before] = [ph, c.slice(0, i)];
          }
        }
        if (p && type === 'tests' && admits && COUNT.test(before)) continue;
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
  // "Fixed. All unit tests pass.": the fix is vouched for by some tests only, so a red suite cannot refute it.
  if (scoped && !seen.has('tests')) for (const c of claims) if (c.type === 'fixed') c.scoped = true;
  return claims;
}
