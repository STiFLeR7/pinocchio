# Runtime Permission Matrix

This document defines the permission configuration mapping repositories, allowed runtimes, and allowed profiles in Nexus under AP-304.

---

## 1. Governance Permissions Mapping

Under the hardened governance framework, a task can only execute if the requested runtime and execution profile are authorized by the target repository registry record.

The table below outlines common permission matrices:

| Repository Name | Target Directory | Allowed Runtimes | Allowed Profiles | Enforcement Action |
| --- | --- | --- | --- | --- |
| **`nexus`** | `D:/projects/nexus` | `["gemini", "claude"]` | `["coding", "analysis"]` | Gemini CLI and Claude CLI are allowed to write code. Nexus Agent is blocked. |
| **`memex`** | `D:/projects/memex` | `["claude"]` | `["refactoring"]` | Only Claude is allowed to run refactoring profiles. |
| **`research`** | `D:/projects/research` | `["nexus"]` | `["research", "reporting"]` | Nexus Agent is authorized to run research goals. Subprocess commands are blocked. |

---

## 2. Enforcement Sequence

The authorization resolution runs sequentially:
1. **Repository Lookup**: The working directory path matches the registered repository absolute path.
2. **Runtime Verification**: The task's `runtime_id` (e.g., `claude`) must exist in the repository's `allowed_runtimes` array. If the array is empty or null, it defaults to unrestricted (but still checked against platform approved list).
3. **Profile Verification**: The task's `execution_profile` (e.g., `coding`) must exist in the repository's `allowed_profiles` array. If not authorized, a `PolicyViolation` audit log is committed.
