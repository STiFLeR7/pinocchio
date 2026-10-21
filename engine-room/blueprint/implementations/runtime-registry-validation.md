# Runtime Registry Validation Report

This report documents how the **Runtime Registry** resolves execution adapters dynamically in Nexus, satisfying AP-302B requirements.

---

## 1. Decoupled Dynamic Discovery

Prior to AP-302B, the orchestrator selected runners using hardcoded string-matching branches. Under the new **Runtime Registry** architecture, discovery is entirely decentralized:

1. Runtimes register themselves dynamically using the `@runtime_registry.register("runner_id")` decorator.
2. The orchestrator delegates runner lookup to `get_runtime_adapter`, which retrieves the registered class from `runtime_registry`.
3. The orchestrator instantiates the resolved adapter and executes it using polymorphic interfaces (`CLIRuntimeAdapter` or `AgentRuntimeAdapter`), with no awareness of the specific runner's type.

---

## 2. Verified Registrations

The registry maps keys to implementations:

| Key | Implementation Class | Interface |
| --- | --- | --- |
| `"gemini"` | `GeminiRuntimeAdapter` | `CLIRuntimeAdapter` |
| `"claude"` | `ClaudeRuntimeAdapter` | `CLIRuntimeAdapter` |
| `"nexus"` | `NexusRuntimeAdapter` | `AgentRuntimeAdapter` |

### Adding a Runtime (Zero Orchestrator Churn)

Adding Claude required zero changes to [orchestrator.py](file:///D:/nexus/nexus/scheduling/orchestrator.py):

```python
# Resolved inside runners/__init__.py:
cls = runtime_registry.get_adapter_cls(runner_name)
return cls(db_session, execution_id, ...)
```

If we need to introduce a future runner like `Claude Code` (interactive) or `ResearchWorker`, we simply register the class. The orchestrator continues to route correctly, making runtime discovery highly auditable and extensible.
