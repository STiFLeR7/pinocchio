const BUILTIN = {
  fixed: ['fixed', 'resolved', 'works now', 'is working now'],
  tests: ['tests pass', 'tests passed', 'tests are passing', 'tests now pass', 'all tests pass', 'all tests passed', 'all green', 'suite passes', 'test suite passes', 'tests passing', 'all tests passing', 'tests are green', 'tests succeeded'],
};
const NEGATION = /(\bnot\b|n't\b|\bnever\b|\bunable\b|\bcannot\b|\byet to\b|\bfail(s|ed|ing)?\b)/i;
const HEDGE = /\b(should|would|could|might|may|need|needs|to be|if|once|when|whether|can be|will)\b/i;

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

  // Split by sentence boundaries
  for (const s of text.split(/(?<=[.!?\n])\s+/)) {
    // Extract file claims at sentence level (NEGATION skips them per sentence)
    if (!NEGATION.test(s)) {
      // Find all matches of verbs followed by backticked paths
      const verbPattern = '(?:updated|changed|modified|edited|added to|fixed)';
      const fileVerbRegex = new RegExp('\\b' + verbPattern, 'gi');
      let verbMatch;
      while ((verbMatch = fileVerbRegex.exec(s)) !== null) {
        const afterVerb = s.substring(verbMatch.index + verbMatch[0].length);
        const backtickRegex = /`([^`]+)`/g;
        let backtickMatch;
        while ((backtickMatch = backtickRegex.exec(afterVerb)) !== null) {
          const cleaned = backtickMatch[1];
          if (isPathLike(cleaned) && !cleaned.includes(' ') && !cleaned.includes('(')) {
            const key = `file:${cleaned}`;
            if (!seen.has(key)) {
              seen.add(key);
              claims.push({ type: 'file', text: backtickMatch[0], file: cleaned });
            }
          }
        }
      }
    }

    // Split into clauses for tests/fixed matching
    const clauses = s.split(/[,;:]|\s+but\s+|\s+—\s+/i);
    for (const clause of clauses) {
      const c = clause.trim();
      if (!c || NEGATION.test(c) || HEDGE.test(c)) continue;

      for (const type of ['fixed', 'tests']) {
        if (seen.has(type)) continue;
        const p = phrases[type].find((ph) => hasPhrase(c, ph));
        if (p) {
          seen.add(type);
          claims.push({ type, text: p });
        }
      }
    }
  }
  return claims;
}
