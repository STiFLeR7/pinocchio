# Agent Artifact Persistence Report

This report verifies that Nexus first-class agent artifacts and reasoning steps coexist successfully with standard CLI subprocess artifacts in the Nexus database schema.

---

## 1. Coexistence of CLI and Agent Artifacts

Under Runtime V2, `ExecutionArtifactRecord` holds artifacts for both paradigms using custom `artifact_type` scopes:

* **Subprocess CLI Runner (Gemini)**:
  * `stdout.log` (type: `stdout`): Capture of raw terminal outputs.
  * `stderr.log` (type: `stderr`): Standard error traces.
  * `summary.md` (type: `summary`): Markdown brief.
  * `changes.diff` (type: `diff`): Code modification patches.
* **Autonomous Agent Runner (Nexus)**:
  * `plan.json` (type: `agent_plan`): Sequential plan deconstruction.
  * `trajectory.json` (type: `agent_trajectory`): Serialized JSON array of thoughts, tool calls, and observations.
  * `summary.md` (type: `summary`): Synthesis brief of findings.
  * `changes.diff` (type: `diff`): Local repository changes.

---

## 2. SQL Database Inspection Verification

Querying the SQL database after running the E2E verification script shows that both step trajectories and custom artifact entities are persisted correctly:

### A. Trajectory Steps (`agent_steps` table):
| Step Index | Thought | Tool Name | Tool Input | Tool Result |
| :--- | :--- | :--- | :--- | :--- |
| `0` | I need to research MCP developments | `web_search` | `{"query": "MCP developments"}` | Search results containing FastMCP SDK info... |
| `1` | I will write findings report to file | `write_file` | `{"path": ".\\mcp_report.md", ...}`| File written successfully... |
| `2` | Task completes successfully | `finish` | `{}` | Agent completed execution. |

### B. Captured Artifacts (`execution_artifacts` table):
| Name | Type | Size (Bytes) |
| :--- | :--- | :--- |
| `plan.json` | `agent_plan` | 253 |
| `trajectory.json`| `agent_trajectory` | 995 |
| `summary.md` | `summary` | 75 |
| `changes.diff` | `diff` | 3347 |
