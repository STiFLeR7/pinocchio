# Track S Closure Review — Sandbox Hardening (S-2 · S-3 · S-4)

> **Release line:** v1.1.0 "Containment" · **Scope:** Track S only · **Type:** evidence-based review
> (no code/test/implementation changes). **Method:** claims re-verified against current source +
> live test/lint/type run (project venv `.venv/Scripts/python.exe`).
> **Baseline audit:** A-006 (`sandbox-safety-review.md`, `sandbox-risk-register.md`,
> `ADR-sandbox-safety-review.md`). **Verdict:** see §9 and `ADR-sandbox-pilot-safe.md`.

---

## 1. Purpose

A-006 classified the execution sandbox **"Unsafe By Default"** and produced a 9-risk register
(R-01…R-09). Track S (S-2, S-3, S-4) was the separately-authorized hardening sequence. This review
establishes, from repository evidence only, **what was closed, what remains, and whether the
subsystem can be formally reclassified Experimental → Pilot Safe.**

It introduces no new code, tests, or design. Every claim below was re-verified against the current
working tree (HEAD `2fd3ffc`, Track S changes staged but uncommitted).

## 2. Scope reviewed

| AP | Title | Risks targeted | Source-verified location |
|---|---|---|---|
| **S-2** | Default-Secure Sandbox Resolution | R-01, R-02 | `manager.py:34-64`, `exceptions.py:86-91` |
| **S-3** | Sandbox Enforcement & Startup Validation | R-03, R-06, R-07 | `provider.py:62-73,146,151-170,296-300`, `manager.py:121,196-256`, `api.py:106-113`, `exceptions.py:94-99` |
| **S-4** | Workspace Confinement & R-05 Closure | R-05 | `confinement.py`, `nexus.py:16,75-117`, `exceptions.py:102-107` |

> **Note on the risk-set framing.** The closure request referenced "R-01 through R-07". The
> authoritative A-006 register actually spans **R-01 through R-09**. This review covers the full set
> for honesty; R-04, R-08, R-09 are addressed in §5 (Residual) and §6 (Deferred).

## 3. Live verification (this review)

| Gate | Command | Result |
|---|---|---|
| Full suite | `pytest -q` | **178 passed** in ~35s |
| Lint | `ruff check nexus/ tests/` | **All checks passed!** |
| Types | `mypy nexus/ --ignore-missing-imports` | **no issues in 58 source files** |
| HEAD | `git rev-parse --short HEAD` | `2fd3ffc` (Track S staged, **uncommitted**) |

Suite progression across the track: 143 (v1.0.1 baseline) → 152 (S-2, +9) → 166 (S-3, +14) →
**178 (S-4, +12)**. **Zero regressions** at any step.

## 4. Resolution status — the targeted risk set

### R-01 — Default config executes on host with zero isolation → **CLOSED (S-2)**
- **Before:** `enabled=False` → `LocalSandboxProvider` → host shell (`provider.py:111` `create_subprocess_shell`).
- **After (verified `manager.py:50-55`):** a real `NexusSettings` with `sandbox.enabled=False` raises
  `SandboxResolutionError` at `SandboxManager.__init__` — **before any sandbox exists**. Implicit host
  execution is no longer reachable.
- **Proof:** `test_disabled_sandbox_fails_closed`, `test_default_production_settings_fail_closed`.
- **Residual nuance:** the non-`NexusSettings` construction path (`settings` is `None`/test double) is
  **deliberately retained** as Local (`manager.py:46-47`) for adapter/e2e construction. Production
  always supplies `NexusSettings` (`orchestrator.py` passes `bot.settings`), so the default-secure
  guarantee holds in production. Documented, not a defect.

### R-02 — Unknown/misspelled provider fails open to host → **CLOSED (S-2)**
- **Before:** `else: return LocalSandboxProvider()` (`manager.py:52-53` original).
- **After (verified `manager.py:57-64`):** provider matched case-insensitively against
  `RECOGNIZED_PROVIDERS`; an unrecognized name raises `SandboxResolutionError`. **No host fallback.**
- **Proof:** `test_unknown_provider_fails_closed`, `test_unknown_provider_cannot_execute`.

### R-03 — Containment policy decorative under Local → **CLOSED (honesty), behavior-bounded (S-3)**
- **Before:** policy built/audited then ignored by Local; audit recorded a policy that was not enforced.
- **After (verified `provider.py:65,146`, `manager.py:121`):** every `SandboxProvider` carries
  `enforces_policy` (Docker `True`; Local/Mock/ABC `False`); `sandbox.created` audit now records
  `policy_enforced=self.provider.enforces_policy`. The pretense is ended — a host run is **declared**
  `policy_enforced=false`, not silently mislabelled.
- **Scope honesty:** S-3 made enforcement **honest and boot-gated**, not universal. Local still does
  not enforce limits *by design* — but it can only run via the deliberate, recognized `provider=local`
  opt-in, and that choice is loudly warned at startup (`sandbox_host_unsafe_at_startup`).
- **Proof:** `test_execute_audit_declares_policy_enforcement`, `test_*_enforce_policy_flag`.

### R-05 — Agent file tools bypass the sandbox → **CLOSED at floor (S-4)**
- **Before:** `nexus.py` `read_file`/`write_file` used raw `open()` on any host path, no confinement.
- **After (verified `nexus.py:96-117`, `confinement.py`):** both tools resolve through
  `resolve_in_workspace(await self._workspace_cwd(), path)` before any FS access. `resolve()` collapses
  `..`, follows symlinks; `is_relative_to(workspace)` rejects escape → `WorkspaceConfinementError`
  (fail-closed, no `open`/`makedirs`). The workspace is `ExecutionRecord.repository` — the same cwd
  used for command execution, giving one boundary for all execution paths.
- **Proof:** `test_nexus_read_escape_denied`, `test_nexus_write_escape_denied`,
  `test_parent_traversal_denied`, `test_deep_traversal_denied`,
  `test_confinement_independent_of_provider`.
- **Closed "at floor":** the host-side path-confinement floor eliminates the escape; the in-container
  file-I/O ceiling is deferred defense-in-depth (§6).
- **Residual nuance:** when `ExecutionRecord.repository` is empty, `_workspace_cwd()` falls back to
  `"."` (`nexus.py:80`) — the process cwd, identical to the command-execution cwd default. The
  confinement guarantee still holds *relative to that workspace*; bounding the workspace itself is an
  operator responsibility (workspace = approved repository by design).

### R-06 — No Docker availability validation → **CLOSED (S-3)**
- **After (verified `provider.py:151-170`, `manager.py:238-244`):**
  `DockerSandboxProvider.ensure_available()` probes `docker version`; `FileNotFoundError` or non-zero
  exit raises `SandboxUnavailableError`. `validate_sandbox_startup` calls it at boot and wraps failure
  into `ConfigurationError` → app aborts. Defense-in-depth: runtime spawn fail-closed
  (`manager.py:186-193`) still refuses if startup is bypassed.
- **Proof:** `test_startup_docker_unavailable_aborts`, `test_docker_ensure_available_raises_when_missing`,
  `test_docker_ensure_available_raises_on_nonzero`.

### R-07 — No sandbox startup/config validation → **CLOSED (S-3)**
- **After (verified `manager.py:196-256`, `api.py:106-113`):** `validate_sandbox_startup(settings)` is
  wired into the lifespan **after** the A-001 owner gate; unknown provider or unavailable enforcing
  provider → `ConfigurationError` logged `critical` and re-raised → **boot aborts** (identical
  discipline to A-001). Disabled/unconfigured → warned (safe; runtime still fails closed via S-2).
- **Proof:** `test_startup_unknown_provider_aborts`, `test_startup_docker_unavailable_aborts`.

### Summary — targeted set

| Risk | Severity (A-006) | Status | AP |
|---|---|---|---|
| R-01 default host exec | 🔴 Critical | **CLOSED** | S-2 |
| R-02 unknown-provider fail-open | 🔴 Critical | **CLOSED** | S-2 |
| R-03 decorative policy | 🔴 High | **CLOSED (honesty + boot gate)** | S-3 |
| R-05 agent file bypass | 🔴 High | **CLOSED (floor)** | S-4 |
| R-06 no docker validation | 🟠 Medium | **CLOSED** | S-3 |
| R-07 no startup validation | 🟠 Medium | **CLOSED** | S-3 |

**Both Critical risks and all targeted High/Medium risks are closed.**

## 5. Residual risks (not in the Track S charter)

| Risk | Severity (A-006) | Status | Why residual / disposition |
|---|---|---|---|
| **R-04** command blacklist is bypassable substring match | 🔴 High | **OPEN** | Governance-owned (`governance.py`/`policy_defaults.py`), not a sandbox-containment defect. Out of Track S scope by design. Mitigated by approval gate + (when isolation on) container. **Recommend a future governance AP.** |
| **R-08** shell-string exec surface (`create_subprocess_shell` / `sh -c`) | 🟠 Medium | **OPEN (design-inherent, bounded)** | Inherent to "run approved arbitrary commands". Impact is **High under Local, Low–Medium under Docker** — and after S-2/S-3 Local runs only via deliberate, boot-warned opt-in; untrusted workloads use Docker where this surface is contained. Acceptable for Pilot. |
| **R-09** `cwd` mounts real repo into container; default `filesystem_policy="restricted"` not `readonly` | 🟡 Low–Med | **PARTIAL** | Docker provider supports `:ro` (`provider.py:196-198`) but default is `restricted`. Writes to the mounted workspace are real host writes within the approved repo. Coherent with the R-05 workspace-as-boundary model; tightening the default to `readonly` is an enhancement, not a Pilot blocker. |

**Residual nuances inside closed risks** (documented above, not blockers): R-01 non-`NexusSettings`→Local
construction path; R-05 empty-repository `"."` workspace fallback.

## 6. Deferred items (explicitly recorded, not silently dropped)

| Item | Owner / track | Rationale |
|---|---|---|
| In-container file I/O under Docker (run file ops *inside* the container) | Track S enhancement | Escape already prevented by the host-side workspace floor; ceiling is defense-in-depth. Under Docker the workspace is the mounted volume. |
| R-04 command-policy hardening | Governance AP | Separate subsystem; not containment. |
| R-09 default `filesystem_policy=readonly` | Track S enhancement | Tightening a default; not required to reach Pilot Safe. |
| R-08 argv/exec-vector hardening | Design-level future work | Trade-off vs. the "run approved commands" product requirement. |
| All Track-H Nexus work (real search/planning, honest exit/terminate, resume) | Track H (A-005/AP-105) | Out of Track S scope; tracked separately. |

## 7. Security posture — before vs after (summary; detail in `track-s-before-after.md`)

| Dimension | Before (A-006) | After (Track S) |
|---|---|---|
| Default behavior | Silent host execution | **Fail-closed** (refuses to run implicitly) |
| Unknown provider | Silent host fallback | **Fail-closed** (`SandboxResolutionError`) |
| Policy honesty | Decorative (recorded, ignored) | **Declared** (`policy_enforced` flag; host run warned) |
| Startup safety | None (unsafe config boots) | **Boot gate** (abort on incoherent/unavailable) |
| Docker availability | Discovered at first command | **Probed at startup** (fail-fast) |
| Agent file tools | Arbitrary host read/write | **Workspace-confined**, fail-closed, provider-independent |
| Containment boundary | Commands only (cwd), files unbounded | **One workspace boundary** for commands + files |
| Audit | Complete (already a strength) | Complete **+ honesty metadata** (`policy_enforced`) |

## 8. Pilot Safe readiness assessment

The A-006 ADR defines isolation as opt-in requiring `enabled=true`, `provider=docker`, Docker present,
recommended `readonly`. The "Unsafe By Default" label rested on four facts; each is now changed **in
code with test evidence**:

1. *Default ran on host silently* → now **fail-closed** (R-01, R-02). ✅
2. *Unknown provider fell open to host* → **fail-closed** (R-02). ✅
3. *Policy was decorative / no startup validation* → **honest + boot-gated** (R-03, R-06, R-07). ✅
4. *Agent file tools bypassed containment* → **workspace-confined** (R-05). ✅

**Pilot Safe (not Production Safe) is the correct target** because:
- Residual R-04 (governance), R-08 (design-inherent shell surface), R-09 (read-only default) remain —
  acceptable under supervised pilot conditions with the approval gate + complete audit, but not the
  zero-residual bar of Production Safe.
- Local/host execution remains *possible* (by deliberate, warned, audited opt-in) — appropriate for a
  pilot, not for unconditional production isolation claims.

**No remaining blockers** exist for the Pilot Safe bar as defined in `ADR-sandbox-v1.1-foundation.md`
and `S-1-sandbox-master-design.md`. All Pilot-gating risks (R-01, R-02, R-03, R-05, R-06, R-07) are
closed with passing tests; the open items are explicitly scoped out and tracked.

## 9. Reclassification determination

**Question:** Can the Sandbox subsystem be formally reclassified Experimental → Pilot Safe using only
evidence currently present in the repository?

**Evidence basis (all present in-repo, re-verified live):**
- Source: `manager.py`, `provider.py`, `confinement.py`, `exceptions.py`, `nexus.py`, `api.py`.
- Tests: `test_sandbox_resolution.py` (9), `test_sandbox_enforcement.py` (14),
  `test_workspace_confinement.py` (12) — all green within **178 passed**; ruff + mypy clean.
- Provenance: S-2/S-3/S-4 implementation + validation deliverables; A-006 register/ADR as baseline.

**Determination:** The six Pilot-gating risks are closed with verifiable, passing evidence; the two
Critical risks are eliminated; residual risks are bounded, out-of-charter, and tracked. The evidence
in the repository is **sufficient and self-contained** to support the reclassification.

> ### Verdict: **APPROVED** — Sandbox subsystem reclassified **Experimental → Pilot Safe**.

**Conditions attached to the classification:**
1. Pilot Safe, **not** Production Safe — R-04, R-08, R-09 remain open and must be disclosed.
2. The reclassification becomes effective in `architecture-status-summary.md` only via a separately
   authorized documentation step (this review performs **no** documentation rewrite outside its four
   deliverables) and on **commit** of the Track S changes (currently uncommitted at HEAD `2fd3ffc`).
3. Production isolation claims still require `enabled=true` + `provider=docker` + Docker present
   (+ recommended `readonly`); host opt-in remains deliberate and audited.

See `ADR-sandbox-pilot-safe.md` for the formal decision record and `track-s-risk-matrix.md` /
`track-s-before-after.md` for the supporting matrices.

## 10. Review constraints honored

No code modified ✅ · no tests modified ✅ · no new implementation ✅ · no documentation rewrites
outside the four requested deliverables ✅ · no commits ✅ · all claims re-verified against current
source + live gates ✅.
