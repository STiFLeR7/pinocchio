# Tutorial 09 — Policy Authoring

## What you'll learn

How Nexus decides whether an action is allowed at all, why the default is deny (not allow), and how to
evaluate a policy decision directly.

## Concept: fail-closed by default

The Policy Engine (`nexus_policy`) is a deterministic, data-driven rule evaluator — never an embedded
scripting language, never an LLM. Given a request and the applicable policies, it returns one of a fixed
set of decisions (`Allow`, `Deny`, `RequireApproval`, `Delay`, `Escalate`, `RequestInformation`). The rule
that matters most: **an action with no matching policy is denied, not allowed through** (INV-30, ADR-004
§3.1). This is the opposite default from most systems, and it's deliberate.

```python
policy = build_policy(infra)
decision = policy.engine.evaluate(DecisionRequest(...))
# decision.outcome, decision.reasoning, decision.matched_policy
```

Conflicts between multiple matching policies resolve in a fixed, deterministic order: **Specificity →
Priority → Version → Default Policy** — never ad hoc, never dependent on registration order.

## Run it

```bash
uv run python examples/03-policy-governance/run.py
```

Read [`examples/03-policy-governance/README.md`](../../examples/03-policy-governance/README.md) — it
evaluates two real `DecisionRequest`s: one allowed, one matching the real seeded
`GLOBAL_COMMAND_BLACKLIST` (e.g. `"rm -rf /"`) and correctly denied.

## What you should see

An explainable decision for each request — not just `Allow`/`Deny`, but the reasoning trace showing which
policy matched and why. (On Windows, this trace includes real Unicode characters — see the example's own
`sys.stdout.reconfigure(encoding="utf-8")` note if you hit a `UnicodeEncodeError`.)

## Check your understanding

- Why does the Policy Engine never decide `Retry`/`Rollback`/`Abort`? (Those are Recovery's decisions, not
  Policy's — ADR-004 §3.2 explicitly separates "is this allowed" from "what do we do about a failure,"
  because conflating them removed a real ownership boundary early in the platform's design history.)
- If you wrote a new policy with the same specificity, priority, and version as an existing one, what would
  decide the winner? (Nothing does — this is exactly the kind of ambiguity ADR-004's conflict-resolution
  order exists to prevent; policies should be authored to avoid it, not rely on unspecified tie-breaking.)

## Go deeper

[`docs/v2/20_POLICY_ENGINE.md`](../v2/20_POLICY_ENGINE.md); [`adr/ADR-004.md`](../../adr/ADR-004.md) for the
full ratified decision, including every alternative considered and rejected.

## Next

[Tutorial 10 — Building Your First Autonomous Workflow](10-autonomous-workflow.md)
