# Runtime Migration Analysis

This report evaluates the database, memory, and schema impacts of migrating from Runtime V1 to Runtime V2. It classifies each impact category by severity and describes migration paths.

---

## 1. Database Table Impact Registry

| Schema Table | Description of Structural Changes | Classification | Migration Action |
| :--- | :--- | :--- | :--- |
| **`tasks`** | No changes. Status definitions are compatible. | **No Impact** | None |
| **`approvals`** | No changes. Approval gate parameters are compatible. | **No Impact** | None |
| **`executions`** | Add nullable column `run_type` (str) to distinguish CLI from Agent. Reuse `logs` and `result` fields. | **Non-Breaking** | None (Nullable column update) |
| **`execution_steps`**| Subprocess-specific columns (`command`, `pid`, `exit_code`, `stdout`, `stderr`) are CLI-only. | **Migration Required** | Split or generalize table columns (see details below) |
| **`execution_artifacts`**| Schema is already generic. Table supports new `artifact_type` formats directly. | **Non-Breaking** | None |
| **`workflow_checkpoints`**| Schema is generic. Supports serializing AgentState directly. | **No Impact** | None |
| **`audit_log`** | Add new event schemas inside JSON payload. Table schema is unchanged. | **No Impact** | None |

---

## 2. Detailed Technical Impact Areas

### A. Execution Steps Refactoring (Migration Required)
The current `execution_steps` table contains fields specific to POSIX OS processes:
* `pid`: integer (nullable)
* `exit_code`: integer (nullable)
* `command`: text
* `stdout` / `stderr`: text (nullable)

**Migration Plan**:
To avoid breaking backward compatibility or locking sqlite databases, we evolve the table columns to support polymorphic step data:
1. **Option A (Polymorphic Table)**: Keep `execution_steps` and relax column constraints. Add `step_type` (e.g. `subprocess`, `tool_call`) and a nullable `metadata` JSON column.
2. **Option B (Separate Table - Recommended)**:
   * Keep `execution_steps` exclusively for CLI subprocess command runs.
   * Add a new `agent_steps` table to store agent trajectory actions:
     ```python
     class AgentStepRecord(TimestampMixin, Base):
         __tablename__ = "agent_steps"
         execution_id = mapped_column(ForeignKey("executions.id", ondelete="CASCADE"), nullable=False)
         step_index = mapped_column(Integer, nullable=False)
         thought = mapped_column(Text, nullable=True)
         tool_name = mapped_column(String(100), nullable=True)
         tool_arguments = mapped_column(JSON, nullable=True)
         tool_result = mapped_column(Text, nullable=True)
         status = mapped_column(String(50), nullable=False)  # running, completed, failed
     ```

### B. Execution Event Models (Non-Breaking)
Events mapped inside `SystemEventRecord` and `AuditLogRecord` tables are stored as raw JSON blobs. Modifying event schemas does not affect DB structural models.
* *Classification*: **Non-Breaking / No Migration Required**.
* *Action*: Update event gateway serialize mappings to support new V2 event keys (e.g., `agent.plan_generated`, `agent.tool_called`).

### C. Execution Artifacts (Non-Breaking)
The existing `execution_artifacts` table is already generic:
```python
class ExecutionArtifactRecord(TimestampMixin, Base):
    execution_id: Mapped[uuid.UUID]
    artifact_type: Mapped[str]
    name: Mapped[str]
    content: Mapped[str | None]
    data: Mapped[dict | None]
```
No table alterations are required. The new runtimes (Claude, Nexus) can insert artifact rows by specifying new type attributes (e.g., `trajectory`, `citations`).
* *Classification*: **Non-Breaking / No Migration Required**.
