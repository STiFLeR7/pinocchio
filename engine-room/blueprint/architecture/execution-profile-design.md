# Execution Profile Design

This document details the configuration and behaviors of **Execution Profiles** in Nexus. Execution profiles map tasks to specific operating parameters, decoupling raw execution runners from behavioral constraints.

---

## 1. Core Profile Definitions

We define the following standard profiles to tailor execution behaviors:

| Profile | Purpose | Timeout (sec) | Checkpoint Freq | Artifact Expectations |
| --- | --- | --- | --- | --- |
| **Research** | Gather information, scrape/analyze pages | 900 | Mid-execution step | Research summaries, raw source references |
| **Planning** | Break complex requirements into subtasks | 600 | Per task branch | Task plan graphs, capability checklist |
| **Coding** | Modify codebase files, run verification tests | 1800 | High (per edit/test) | File diffs, lint checks, test reports |
| **Refactoring** | Clean up architecture, reduce complexity | 2700 | Very High (pre/post refactor)| Structure graphs, regression validation |
| **Analysis** | Scan repositories, construct dependency trees | 1800 | Step completion | Repository index map, module coupling report|
| **Reporting** | Generate executive summaries and system health briefings | 600 | Execution end | Operational report files, briefing texts |
| **Custom** | Overridden user-specified custom workloads | Dynamic | Dynamic | User-defined metadata |

---

## 2. Configuration Resolution

Profiles are resolved prior to execution, adjusting runtime configuration dynamically:

```python
class ProfileManager:
    def __init__(self, settings: NexusSettings) -> None:
        self.settings = settings
        self.profiles = {
            "research": {
                "timeout": settings.execution.research_timeout_seconds,
                "checkpoint_frequency": "step",
                "required_artifacts": ["markdown_summary"],
            },
            "coding": {
                "timeout": settings.execution.gemini_timeout_seconds,
                "checkpoint_frequency": "edit",
                "required_artifacts": ["diff"],
            },
            # Additional mappings...
        }

    def resolve_profile_constraints(self, profile_name: str) -> dict[str, Any]:
        return self.profiles.get(profile_name, self.profiles["default"])
```

---

## 3. Influence on Execution Lifecycle

Execution profiles influence the runner lifecycle hooks:

1. **Timeout Enforcement**: The timeout threshold resolved from the profile sets the task's maximum duration. The execution scheduler aborts tasks exceeding this limit.
2. **Artifact Validation**: During `persist()`, the adapter validates that the expected artifacts (e.g. diffs for "coding", summaries for "research") were generated and persisted.
3. **Checkpoint Frequency**: Determines how frequently the adapter logs state checkins via the `checkpoint()` hook.
