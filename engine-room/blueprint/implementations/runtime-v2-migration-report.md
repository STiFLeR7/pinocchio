# Runtime V2 Database Migration Report

This report documents the database model migrations and schema adjustments completed for the Runtime V2 architecture.

---

## 1. Relational Table Additions

We introduced the [AgentStepRecord](file:///D:/nexus/nexus/memory/models.py#L271-L302) table to hold multi-step agent trajectories:

```sql
CREATE TABLE agent_steps (
    id VARCHAR(36) NOT NULL PRIMARY KEY,
    execution_id VARCHAR(36) NOT NULL,
    step_index INTEGER NOT NULL,
    thought TEXT,
    tool_name VARCHAR(100),
    tool_arguments JSON,
    tool_result TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    last_heartbeat TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    is_archived BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (execution_id) REFERENCES executions(id) ON DELETE CASCADE
);
```

---

## 2. Relationships Mapping

In [models.py](file:///D:/nexus/nexus/memory/models.py#L149-L158), `ExecutionRecord` was extended to declare the `agent_steps` relation:

```python
agent_steps: Mapped[list[AgentStepRecord]] = relationship(
    back_populates="execution",
    cascade="all, delete-orphan",
    lazy="selectin",
)
```

---

## 3. Backward Compatibility Assurance

To ensure zero impact on previously recorded data:
* **Subprocess Steps**: Standard shell runs continue to write to `execution_steps` without modifications.
* **Polymorphic Safety**: SQLite automatically runs migrations on app boot. No schema conflicts or tables conversions were required, making the schema upgrade entirely non-breaking.
