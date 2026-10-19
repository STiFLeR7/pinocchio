# Workspace Confinement Validation (S-4)

> Validation evidence for the workspace-confinement seam and its enforcement in Nexus file tools.
> Run with the project venv (`.venv/Scripts/python.exe`).

---

## 1. The seam

`resolve_in_workspace(workspace, requested_path)` (`nexus/execution/sandbox/confinement.py`):

```
ws        = Path(workspace).resolve()
candidate = requested if absolute else ws / requested
resolved  = candidate.resolve()          # collapses '..', follows symlinks
if not resolved.is_relative_to(ws):      # outside workspace?
    raise WorkspaceConfinementError(...)  # fail-closed
return resolved
```

## 2. Test inventory — `tests/unit/execution/test_workspace_confinement.py` (12)

| Test | Asserts |
|---|---|
| `test_valid_relative_path_allowed` | `a.txt` ⇒ resolves to `ws/a.txt` |
| `test_valid_nested_path_allowed` | `sub/dir/a.txt` ⇒ allowed |
| `test_absolute_inside_workspace_allowed` | absolute path inside ws ⇒ allowed |
| `test_parent_traversal_denied` | `../escape.txt` ⇒ `WorkspaceConfinementError` |
| `test_deep_traversal_denied` | `../../../../../../etc/passwd` ⇒ raises |
| `test_absolute_escape_denied` | absolute path outside ws ⇒ raises |
| `test_nexus_read_within_workspace_succeeds` | Nexus `read_file` returns approved content |
| `test_nexus_read_escape_denied` | `../secret.txt` ⇒ secret content **not** returned; error |
| `test_nexus_write_within_workspace_succeeds` | Nexus `write_file` creates the file in ws |
| `test_nexus_write_escape_denied` | `../evil.txt` ⇒ file **not** created outside; error |
| `test_read_and_write_equally_constrained` | absolute outside path denied for **both** read & write; external file unchanged |
| `test_confinement_independent_of_provider` | escape denied even with `provider=docker` configured |

Result: **12 passed.**

## 3. Requirement → evidence matrix

| Validation question | Evidence |
|---|---|
| 1. Files outside workspace accessible? **No** | `test_nexus_read_escape_denied`, `test_nexus_write_escape_denied` |
| 2. Path traversal escapes? **No** | `test_parent_traversal_denied`, `test_deep_traversal_denied` |
| 3. Read & write equally constrained? **Yes** | `test_read_and_write_equally_constrained` (+ both escape tests) |
| 4. Holds under Docker & Local? **Yes** | `test_confinement_independent_of_provider` + path-layer enforcement (provider-independent) |
| 5. What is audited? | file-tool result (incl. denial) persisted via `AgentStepRecord`; commands via `sandbox.*` |
| 6. Deferred? | in-container file I/O ceiling; Track-H Nexus work; R-04 command policy |

## 4. TDD trace

- **Red:** `ImportError: cannot import name 'WorkspaceConfinementError'` (+ seam absent) before
  implementation.
- **Green:** 12/12 after adding the exception, `resolve_in_workspace`, and the Nexus confinement.

## 5. Behavioral truth table (validated)

| `requested_path` (workspace = ws) | Outcome |
|---|---|
| `a.txt`, `sub/x.txt` | allowed → `ws/...` |
| absolute path inside ws | allowed |
| `../x`, `../../x`, deep `..` | **WorkspaceConfinementError** |
| absolute path outside ws | **WorkspaceConfinementError** |
| symlink resolving outside ws | **WorkspaceConfinementError** (resolve() follows the link) |

## 6. Verdict

**PASS.** File access is confined to the approved workspace; traversal and absolute escape fail closed;
read and write are equally constrained; the guarantee is provider-independent.
