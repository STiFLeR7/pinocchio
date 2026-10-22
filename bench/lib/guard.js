const KEYS = ['ANTHROPIC_API_KEY', 'OPENAI_API_KEY'];

export function assertSubscriptionOnly(env = process.env) {
  for (const k of KEYS) {
    if (env[k]) throw new Error(`${k} is set: the benchmark runs on your subscription only. Unset it and retry.`);
  }
}
