# Nexus Honesty Validation (H-2)

> Evidence that simulation is gone from the Nexus production path and that outcomes are now truthful.
> Covers the **removed-mock inventory** and the **exit-status validation evidence**. All claims verified
> against current source + the H-2 test suite (project venv).

---

## 1. Removed-mock inventory

| Removed item | Was at | Evidence of removal |
|---|---|---|
| `from unittest.mock import AsyncMock` (module import) | `nexus.py:7` | Gone. Guard test `test_no_unittest_mock_import_in_runtime` asserts `unittest.mock`/`AsyncMock` absent from the module source |
| `is_mocked` decision branch | `nexus.py:198-223` | Gone. Guard test asserts `is_mocked` absent from source; the loop has a single real path |
| Canned MCP search text | `nexus.py:84-94` (old) | Gone. `test_no_canned_search_literal_in_runtime` asserts "Model Context Protocol (MCP) is widely adopted" absent |
| Decorative hardcoded plan literal | `nexus.py:159-163` (old) | Gone. Same guard asserts "Search web for MCP ecosystem developments" absent |
| `"test-key"` downgrade heuristic | `nexus.py:200-203` (old) | Gone with the `is_mocked` branch |
| Brittle string-split + keyword `finish` fallback | `nexus.py:224-246` (old) | Replaced by `parse_tool_call` (structured, explicit error) |

**Net:** the runtime no longer imports a test library, no longer branches on a mock condition, and no
longer carries canned search or a decorative plan. Simulation now lives **only** in injected test doubles
(`tests/unit/execution/test_nexus_honesty.py`: `FakeLLMClient`, `FailingLLMClient`, `FakeSearchProvider`).

## 2. Single honest decision path (after)

```
model.complete(prompt)  ─►  parse_tool_call(completion)  ─►  ToolCall{thought, tool_name, tool_arguments}
                                   │ (malformed / unknown tool)
                                   ▼
                          ToolCallParseError  ─►  step status=FAILED, exit_code=1   (NOT a silent finish)
```

No alternate mock branch exists. With no model client injected, the loop fails honestly (recorded as a
`FAILED` step) rather than silently producing canned output.

## 3. Exit-status validation evidence

### 3.1 Behavioral truth table (validated by tests)

| Scenario | Outcome | `exit_code` | `status` | Step status | Test |
|---|---|---|---|---|---|
| Genuine `finish` | completed | `0` | `completed` | COMPLETED | `test_success_yields_zero_exit` |
| Model/transport error | failed | `1` | `failed` | FAILED | `test_failure_yields_nonzero_exit`, `test_failed_step_persisted_with_truthful_status` |
| Malformed tool-call | failed | `1` | `failed` | FAILED | `test_malformed_call_fails_not_silent_finish` |
| Budget exhausted w/o finish | failed (incomplete) | `1` | `failed` | — | covered by loop logic (`if not finished: failed = True`) |

### 3.2 Runtime trace (recorded)

```
=== FAILURE (model transport error -> truthful non-zero exit) ===
  step 0: tool=error status=failed result='Error: model transport failure'
  RETURN: {'exit_code': 1, 'status': 'failed', 'steps_executed': 1, 'trajectory_len': 1}

=== MALFORMED (bad tool-call -> FAILED, not silent finish) ===
  step 0: tool=error status=failed result='Tool-call parse error: ...'
  RETURN: {'exit_code': 1, 'status': 'failed', 'steps_executed': 1, 'trajectory_len': 1}

=== SUCCESS (provider-backed search -> finish) ===
  step 0: tool=web_search status=completed result="[real-provider results for 'nexus']"
  step 1: tool=finish status=completed result='Agent completed execution.'
  RETURN: {'exit_code': 0, 'status': 'completed', 'steps_executed': 2, 'trajectory_len': 2}
```

### 3.3 Orchestrator finalization (no change needed)

`orchestrator.py:227` already computes `exit_status = ExitStatus.SUCCESS if exit_code == 0 else
ExitStatus.FAILURE`. Because Nexus now returns a truthful `exit_code`, a failed agent run **finalizes
`FAILURE`** in task state and audit — the always-`0` masking (AP-105 Gap 3) is closed with **zero**
orchestrator edits. The summary artifact also records the real `exit_code` (`nexus.py` persist).

## 4. `AgentStepRecord` compatibility (preserved)

Every step still writes the same fields (`execution_id`, `step_index`, `thought`, `tool_name`,
`tool_arguments`, `tool_result`, `status`, `last_heartbeat`). The only value-level change: a failed step
writes `ExecutionStatus.FAILED.value` (an **existing** enum value) instead of always `COMPLETED`. No
column added/removed; no migration. Persistence tests
(`test_nexus_execute_and_checkpoint`, `test_nexus_summarize_and_persist`) remain green.

## 5. Verdict

Production mock paths are **removed and guard-tested absent**; outcomes are **truthful** (success vs
failure distinguished, persisted, and finalized). Honesty objectives (AP-105 Gaps 1–3, 6) are closed.
