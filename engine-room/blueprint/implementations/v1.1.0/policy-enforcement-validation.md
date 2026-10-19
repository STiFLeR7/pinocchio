# Policy Enforcement Validation (S-3)

> Validation evidence for "enforce policy-or-refuse" — that the containment policy is genuinely enforced
> by the enforcing provider (Docker), that the enforcing provider must be available or we refuse, and
> that non-enforcement (host/local) is honestly declared rather than pretended (R-03).

---

## 1. The R-03 defect (recap, A-006)

The `SandboxPolicy` (cpu/memory/network/filesystem) was built and audited for **every** provider but
**ignored by the Local provider** (`provider.py` Local `spawn` runs a raw host shell). The audit
therefore *pretended* enforcement that did not occur — "decorative policy."

## 2. The S-3 model — enforce, refuse, or declare

| Provider | `enforces_policy` | Behavior |
|---|---|---|
| Docker | **True** | Genuinely enforces via `--cpus`/`--memory`/`--network`/`-v` (`provider.py` Docker `spawn`); **must be available or startup refuses** (R-06) |
| Local (host) | **False** | Does not enforce; allowed only as a deliberate choice; **declared** (`policy_enforced=false` audit + loud startup warning) |
| Mock | **False** | Test provider; non-enforcing; declared |

"Enforce policy-or-refuse" is realized as: **enforce** (Docker) · **refuse** (Docker unavailable →
startup abort / spawn fail-closed) · **declare-not-pretend** (Local/Mock honest audit + warning).

## 3. Honest audit (ends the pretense)

The `sandbox.created` audit event now carries `policy_enforced = provider.enforces_policy`
(`manager.execute`). A host (local) execution records `policy_enforced=false`; a Docker execution
records `policy_enforced=true`. The immutable ledger therefore tells the truth about whether the
recorded policy was actually applied.

## 4. Test inventory

| Test | Asserts |
|---|---|
| `test_docker_enforces_policy_flag` | `DockerSandboxProvider.enforces_policy is True` |
| `test_local_does_not_enforce_policy_flag` | `LocalSandboxProvider.enforces_policy is False` |
| `test_mock_does_not_enforce_policy_flag` | `MockSandboxProvider.enforces_policy is False` |
| `test_execute_audit_declares_policy_enforcement` | `sandbox.created.data.policy_enforced is False` for a mock (non-enforcing) run |
| `test_startup_docker_unavailable_aborts` | enforcing provider unavailable ⇒ refuse (startup abort) |
| `test_startup_local_host_unsafe_passes` | non-enforcing provider ⇒ allowed + warned (declared) |

(Existing `test_docker_sandbox_command_construction` continues to prove Docker maps policy → real
`docker run` flags — i.e. enforcement is real, not nominal.)

## 5. Requirement → evidence

| Requirement | Evidence |
|---|---|
| Policy enforced by enforcing provider | `test_docker_enforces_policy_flag` + existing docker command-construction test |
| Policy cannot be enforced ⇒ fail closed | `test_startup_docker_unavailable_aborts` (refuse) + spawn fail-closed (preserved) |
| Non-enforcement declared, not pretended | `test_execute_audit_declares_policy_enforcement`, `test_local_does_not_enforce_policy_flag` |

## 6. Explicit proof — policy-enforcement failures fail closed

The enforcing provider is Docker; the only way to actually enforce cpu/memory/network/fs is via Docker.
If Docker (the enforcement mechanism) is unavailable, policy **cannot** be enforced — and the system
**refuses**: startup aborts (`test_startup_docker_unavailable_aborts`), and any bypassed runtime attempt
hits the Docker spawn fail-closed. There is no path where a restrictive policy is requested and silently
unenforced under the enforcing provider.

## 7. Verdict

**PASS.** Policy is genuinely enforced by Docker; an unavailable enforcer causes refusal; host execution
is honestly declared (`policy_enforced=false`) and warned, never pretended. R-03 is closed.
