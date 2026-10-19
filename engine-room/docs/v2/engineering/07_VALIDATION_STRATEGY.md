# Validation Strategy

Status: Target Architecture (design only)

---

# Purpose

This document defines how Engineering Intelligence expresses **validation rigor and evidence
intent**, and why that never crosses into determining completion, which is Validation's alone
(INV-20, INV-21).

---

# The hard boundary: rigor vs. verdict

Two different questions, two different owners:

| Question | Owner |
|---|---|
| "How strong must the completion bar be, and what evidence classes matter?" | **Engineering Intelligence** |
| "Given actual evidence, is the work complete?" | Validation (INV-20) |

EI sets the *bar*. Validation *clears or fails against* the bar using independently observable
evidence. EI never sees execution output and never renders a verdict.

---

# What EI produces: Validation Rigor

A **Validation Rigor** facet in the Engineering Strategy is:

- a **rigor level** — how demanding completion must be (e.g., `light`, `standard`, `high`,
  `production-grade`);
- **mandatory evidence classes** — the kinds of evidence that *must* be present for completion to be
  even considerable (e.g., passing regression tests, unchanged public contract, reproduced-then-
  fixed defect, generated-and-reviewed artifact);
- **rationale** tying rigor to risk and classification (INV-31).

Example:

```
Validation Rigor:
  level: high
  mandatory evidence: [ defect reproduced then no longer reproduces,
                        regression suite green,
                        no unrelated diff ]
  rationale: partner-reported production-adjacent bug; a runtime self-report of "fixed" is
             insufficient (INV-20) — evidence must be independently observable
```

EI declares *what would count as done well*. It does not decide *whether it is done*.

---

# Why this strengthens INV-20 rather than competing with it

INV-20 says Validation never trusts runtime self-reporting — completion comes from independently
verifiable evidence. Engineering Intelligence reinforces this from above:

- EI **pre-declares** the evidence classes that matter for *this* work, so Validation is not left to
  infer the bar from a generic default.
- EI can raise rigor for high-risk work (a coherence rule links rigor to the risk envelope, `04`,
  `09`), ensuring the completion bar scales with blast radius.
- EI can never *lower* the bar below what Validation independently requires; it sets intent, and
  Validation remains the sole authority that a given body of evidence clears it.

The result: Validation keeps its verdict monopoly, but now judges against a *work-appropriate* bar
that engineering judgment set, instead of a one-size default.

---

# What EI does NOT do

- **Does not collect or produce evidence.** Execution produces Evidence Candidates; Validation
  produces Evidence (INV-12). EI produces neither.
- **Does not determine completion.** Only Validation does (INV-20/21). A high-rigor Strategy does
  not mean "this passed"; it means "this must clear a high bar to pass."
- **Does not run validators.** EI names evidence *classes*; Validation chooses and runs the
  validators that yield them.
- **Does not override recovery.** If evidence is insufficient, Recovery decides continuation
  (INV-21/22); EI's rigor merely defined what "insufficient" means for this work.

---

# Relationship to the Skill's own validation strategy

A Skill carries its own validation strategy (`../06`). These do not conflict:

- The **Skill** says how *that capability's* output is typically verified (a Testing skill knows it
  produces a test report).
- **EI's Validation Rigor** says how demanding the *overall completion bar* is for *this goal* and
  which evidence classes are mandatory across the composition.

EI's rigor is the ceiling the composed work is held to; the Skills contribute the evidence. Where
the Skill's default rigor is below what the goal's risk demands, EI's facet raises it; Validation
enforces the higher bar.

---

# Boundary summary

| Validation Strategy facet | Enforced by |
|---|---|
| ✓ EI declares rigor level | own responsibility |
| ✓ EI declares mandatory evidence classes | strengthens INV-20 |
| ✓ EI scales rigor with risk | coherence rule (`04`, `09`) |
| ✗ EI never produces evidence | Execution/Validation (INV-12) |
| ✗ EI never determines completion | Validation (INV-20/21) |
| ✗ EI never runs validators | Validation |
| ✗ EI never decides continuation on failure | Recovery (INV-22) |

---

# North Star

Engineering Intelligence sets the bar for "done well."

Validation decides, from evidence alone, whether the bar was cleared. EI raises the standard; it
never signs the certificate.
