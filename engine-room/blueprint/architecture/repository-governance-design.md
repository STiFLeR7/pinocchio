# Repository Governance Design

This document details the security and governance architecture designed to prevent AI runtimes from performing out-of-bounds or destructive operations inside local filesystems.

---

## 1. Governance Concept

Every subprocess executed by an AI runtime in Nexus must pass verification checks before a shell session or process thread is launched. No execution may proceed without formal authorization:

```
        AI Runtime Task Trigger
                  |
                  v
+-----------------+------------------+
|        GovernanceManager           |  (Enforces Allowed Paths, Branch Limits)
+-----------------+------------------+
                  |
                  +--- Fail ---> Raise RepositoryGovernanceError
                  |
                  +--- Pass ---> Spawn OS Subprocess
```

---

## 2. Database Schema: RepositoryRegistryRecord

A new database model, [RepositoryRegistryRecord](file:///D:/nexus/nexus/memory/models.py), will catalog approved project directories and write permissions:

```python
class RepositoryRegistryRecord(BaseModel):
    """ORM database record registering allowed directories and execution rules."""
    __tablename__ = "repository_registry"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    absolute_path: Mapped[str] = mapped_column()
    allowed_branches: Mapped[str] = mapped_column()  # JSON list (e.g. '["dev", "feature/*"]')
    allowed_commands: Mapped[str] = mapped_column()  # JSON list of patterns
    timeout_limit_seconds: Mapped[int] = mapped_column(default=3600)
    is_active: Mapped[bool] = mapped_column(default=True)
```

---

## 3. Validation Logic & Rules

The [GovernanceManager](file:///D:/nexus/nexus/execution/governance.py) performs five sequential validation gates before allowing a subprocess to start:

### Gate 1: Path Boundary Validation
Verify that the target execution path is resolved, active, and resides strictly inside one of the registered `absolute_path` folders.
* **Logic**:
  ```python
  clean_working_dir = os.path.realpath(target_working_dir)
  clean_repo_dir = os.path.realpath(repo_record.absolute_path)
  if not clean_working_dir.startswith(clean_repo_dir):
      raise RepositoryGovernanceError("Path traversal or out-of-bounds execution detected.")
  ```

### Gate 2: Branch Constraints
Ensure that the target repository's current active branch matches the wildcard patterns stored in `allowed_branches`. This prevents write operations directly to `main` or `master`.
* **Logic**: If active branch is `main` and branch policies restrict writes to `dev` or `feature/*`, block execution.

### Gate 3: Command Filter
Scan command strings to verify that they do not match blacklisted shell syntax patterns (e.g., `rm -rf /`, `sudo`, `mv /etc`).

### Gate 4: Timeout Guard
Enforce execution timeout limits on the runner process to prevent hanging scripts.

---

## 4. Exceptions

Governance failures raise [RepositoryGovernanceError](file:///D:/nexus/nexus/core/exceptions.py), which inherits from `ExecutionEngineError`. This ensures that any validation failure is logged, audited, and triggers task failure status updates immediately.
