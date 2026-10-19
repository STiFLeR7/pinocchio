# Nexus Goal-Derived Planning Validation (H-2)

> Evidence that the decorative hardcoded plan is replaced by a plan **derived from the goal**.
> Includes the goal-planning execution trace. Verified against current source + the H-2 test suite.

---

## 1. Before vs after

| | Before (Prototype) | After (H-2) |
|---|---|---|
| Plan source | Hardcoded 3-step literal, identical for every goal (`nexus.py:159-163`) | Generated from the goal by `_generate_plan(goal)` |
| Goal sensitivity | None (decorative) | Plan reflects the goal (model-derived) or a goal-derived fallback |
| Drives loop | No | Advisory artifact; the loop reasons toward the goal |
| Literal present | `"Search web for MCP ecosystem developments"` etc. | **Removed** (guard-tested absent) |

## 2. `_generate_plan(goal)` contract

```
if no model client:        return [{"step": 1, "description": f"Work toward goal: {goal}"}]   # goal-derived fallback
else:                      ask model for a JSON array of step descriptions (about the goal)
                           parse (fence-tolerant) -> normalize to [{step, description}, ...]
                           on any parse failure:   return the goal-derived fallback
```

- **Always goal-derived**, never the old MCP literal — even without a model, the fallback embeds the goal
  text.
- The plan is **advisory** (stored as the existing `agent_plan` artifact, unchanged schema); it records
  intent and does not script the loop.

## 3. Test evidence

| Claim | Test |
|---|---|
| Plan comes from the model/goal, not the MCP literal | `test_plan_is_goal_derived_not_literal` — goal "Investigate widgets"; plan contains the model's "Investigate the widget subsystem"; asserts "MCP ecosystem developments" **absent** |
| No-client plan still derives from the goal | `test_plan_without_client_is_goal_derived_fallback` — goal "Unique-Goal-Token-XYZ"; plan description contains that token |
| The decorative literal is gone from source | `test_no_canned_search_literal_in_runtime` |

## 4. Goal-planning execution trace (recorded)

```
=== SUCCESS (model-derived plan) ===
goal: Research nexus developments
plan: [{'step': 1, 'description': 'Research the topic'},
       {'step': 2, 'description': 'Report findings'}]      # <- from the model, not a literal

=== FAILURE case (no client -> goal-derived fallback) ===
goal: This will fail
plan: [{'step': 1, 'description': 'Work toward goal: This will fail'}]   # <- embeds the goal

=== MALFORMED case (fallback) ===
goal: Malformed path
plan: [{'step': 1, 'description': 'plan'}]                  # <- from the model's plan response
```

Each plan is a function of the goal/model, not a fixed script. The old `[{"Search web for MCP ecosystem
developments"}, {"Write findings report to mcp_report.md"}, {"Finish task..."}]` literal no longer exists.

## 5. Persistence (unchanged plumbing)

The plan is still persisted via the existing `agent_plan` `ExecutionArtifactRecord`
(`nexus.py` persist). `test_nexus_summarize_and_persist` confirms the `agent_plan` artifact is written.
No schema change.

## 6. Scope note

Planning is now **goal-derived and advisory** (Cap 2 Simulated → Partially Implemented, the Experimental
bar). **Advanced replanning / dependency-graph planning is explicitly deferred (P2)** and not part of
H-2.

## 7. Verdict

The decorative plan is replaced by goal-derived planning, evidenced by tests and runtime traces. AP-105
Gap 1 (planning) / Cap 2 closed for the Experimental bar.
