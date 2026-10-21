import path from 'node:path';

export const PLACEBO_TEXT = 'Before you say you are done or that tests pass, verify it: run the tests after your last edit and only claim what you saw.';

// --model short names; any other value is passed to the CLI as given.
export const MODELS = { sonnet: 'claude-sonnet-5-5', haiku: 'claude-haiku-4-5-20251001' };
export const modelId = (model) => MODELS[model] ?? model;

// --strict-mcp-config with no --mcp-config loads no MCP server: the owner's own servers (some can write outside the run) stay out.
export function claudeArgv(arm, prompt, { repoRoot, model }) {
  const argv = ['-p', prompt, '--output-format', 'stream-json', '--verbose', '--setting-sources', 'project,local', '--permission-mode', 'bypassPermissions', '--max-turns', '30', '--strict-mcp-config'];
  if (model) argv.push('--model', modelId(model));
  if (arm === 'on') argv.push('--plugin-dir', repoRoot);
  if (arm === 'placebo') argv.push('--plugin-dir', path.join(repoRoot, 'bench', 'placebo'));
  return argv;
}

export function codexArgv(arm, prompt, dir, model) {
  const p = arm === 'placebo' ? `${PLACEBO_TEXT}\n\n${prompt}` : prompt;
  return ['exec', '--json', '--skip-git-repo-check', '-s', 'workspace-write', '-C', dir, ...(model ? ['-m', modelId(model)] : []), p];
}
