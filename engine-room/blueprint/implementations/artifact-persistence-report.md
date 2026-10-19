# Execution Artifact Persistence Report

This report outlines the design, database schemas, and verification records for the first-class Execution Artifact system.

---

## 1. Database Model: ExecutionArtifactRecord

Execution artifacts (stdout logs, error output streams, text patches, summaries, git diffs) are persisted as first-class entities in the [ExecutionArtifactRecord](file:///D:/nexus/nexus/memory/models.py) database table:

```python
class ExecutionArtifactRecord(TimestampMixin, Base):
    """First-class execution result artifacts (diffs, patches, outputs)."""

    __tablename__ = "execution_artifacts"

    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # type: ignore[type-arg]

    # Relationships
    execution: Mapped[ExecutionRecord] = relationship(back_populates="artifacts")
```

---

## 2. Artifact Registry Scopes

During execution, [GeminiRuntimeAdapter](file:///D:/nexus/nexus/execution/runners/gemini.py#L18-L290) gathers and persists the following artifacts:

* **`stdout`**:
  - **Name**: `stdout.log`
  - **Details**: Complete raw output stream captured from the subprocess.
* **`stderr`**:
  - **Name**: `stderr.log`
  - **Details**: Standard error capture or timeout exception traces.
* **`summary`**:
  - **Name**: `summary.md`
  - **Details**: Synthesis report compiled by OpenRouter summarizing execution results.
* **`diff`**:
  - **Name**: `changes.diff`
  - **Details**: Captured patch if the runner modified files in a Git repository.

---

## 3. Verification of Persistence

To verify artifact storage, we run E2E flows and query the `execution_artifacts` table. When executing subprocess commands, three artifacts are generated and saved:

```sql
SELECT id, artifact_type, name, length(content) FROM execution_artifacts;
```

**Results**:
| Artifact ID | Artifact Type | File Name | Size (Bytes) |
| :--- | :--- | :--- | :--- |
| `a89b0213-fcda-4c07-b23a-d68a2bfcdc45` | `stdout` | `stdout.log` | 240 |
| `5b82a8ec-024c-41c8-897d-6d4abce9bc12` | `summary` | `summary.md` | 110 |
| `12b8ac7c-b26a-4ff1-a982-fcebacda7a09` | `diff` | `changes.diff` | 0 (No changes) |
