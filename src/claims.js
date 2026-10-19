const BUILTIN = {
  fixed: ['fixed', 'resolved', 'works now', 'is working now', 'verified', 'done'],
  tests: ['tests pass', 'tests passed', 'tests are passing', 'tests now pass', 'all tests pass', 'all tests passed', 'all green', 'suite passes', 'test suite passes'],
};
const NEGATION = /(\bnot\b|n't\b|\bnever\b|\bunable\b|\bcannot\b|\byet to\b|\bfail(s|ed|ing)?\b)/i;
const FILE_CLAIM = /\b(?:updated|changed|modified|edited|added to|fixed)\s+`([^`]+)`/gi;

const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const hasPhrase = (sentence, phrase) => new RegExp(`(^|[^a-z])${escape(phrase)}([^a-z]|$)`, 'i').test(sentence);

export function matchClaims(text, config) {
  if (typeof text !== 'string' || !text.trim()) return [];
  const phrases = {
    fixed: [...BUILTIN.fixed, ...config.claimPhrases.fixed],
    tests: [...BUILTIN.tests, ...config.claimPhrases.tests],
  };
  const claims = [];
  const seen = new Set();
  for (const s of text.split(/(?<=[.!?\n])\s+/)) {
    if (NEGATION.test(s)) continue;
    for (const type of ['fixed', 'tests']) {
      if (seen.has(type)) continue;
      const p = phrases[type].find((ph) => hasPhrase(s, ph));
      if (p) {
        seen.add(type);
        claims.push({ type, text: p });
      }
    }
    for (const m of s.matchAll(FILE_CLAIM)) {
      const key = `file:${m[1]}`;
      if (!seen.has(key)) {
        seen.add(key);
        claims.push({ type: 'file', text: m[0], file: m[1] });
      }
    }
  }
  return claims;
}
