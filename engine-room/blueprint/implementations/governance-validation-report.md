# Governance Validation Report

This report documents the validation rules enforced by the **Repository Governance Layer** to prevent unauthorized command execution in Nexus.

---

## 1. Branch Governance

To prevent runtimes from performing un-reviewed modifications on production branches, we enforce branch checks:
* **`allowed_branches`**: If defined, execution is rejected unless the active Git branch matches a pattern (e.g. `["feature/*"]`).
* **`blocked_branches`**: Wildcard patterns specifying branches where execution is forbidden (e.g. `["release/*"]`).
* **`protected_branches`**: Core branches (e.g. `["main", "master"]`) where execution is blocked to prevent accidental direct writes.

---

## 2. Owner Approval Validation

We enforce that the task approval record was granted by a user explicitly listed as an owner of the repository:
```python
authorized_owners = [o.strip() for o in matching_repo.owner.split(",")]
if str(approval.decided_by) not in authorized_owners:
    raise RepositoryGovernanceError(...)
```
This ensures high-risk repositories can only run tasks approved by their designated owners.

---

## 3. Active Execution Limits

To prevent runaway agent loops from consuming host resources or API credits, we enforce concurrent execution limits per repository:
* The system counts database execution records where `completed_at` is null.
* If active executions match or exceed a limit of **3**, new validations are blocked with an `ExecutionBlocked` audit log.
