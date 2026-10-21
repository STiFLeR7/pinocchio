# Nexus — Technical Debt Backlog (post-v1.1.0)

> Every item is **evidence-backed** — observed during the v1.1.0 operational bring-up (2026-06-25).
> No speculative debt. Source reports in `blueprint/implementations/v1.1.0/`.

---

| # | Debt | Severity | Evidence (v1.1.0) | Resolution direction |
|---|---|---|---|---|
| D-1 | Free-tier LLM rate-limits under sustained load | High | OpenRouter 402 (no credits) then free-tier 429; mitigated by Groq→Zenmux→OpenRouter chain but not eliminated | Paid/BYOK key path + provider-exhaustion alerting |
| D-2 | `create_all`-only schema management | High | On-disk schema drift required a manual DB backup + recreate during bring-up; Alembic incomplete | Adopt Alembic migrations; runbook removes manual recreate |
| D-3 | Discord channel routing not config-driven | Medium | `.env` `DISCORD_*_CHANNEL` ids unread; delivery relied on `settings.discord.channels` name resolution | Read channel ids into `settings.discord.channels` |
| D-4 | Gemini / Claude runtimes are generic shell runners | Medium | Classified Experimental; no real model integration | Implement + validate real CLI runtime integration |
| D-5 | No production web SearchProvider | Medium | Agent web tools lack a real provider | Integrate a production search backend |
| D-6 | In-code version string stale (`0.1.0`) | Low | `nexus/__init__.py` / `pyproject.toml` read `0.1.0` while tag is `v1.1.0`; pre-existing, carried from v1.0.x | Align version strings to release tags |
| D-7 | J5/J6 health jobs are read-only snapshots without alerting | Low | Outbox/checkpoint health gauges recorded but no alerting; no soak test run | Add alerting + multi-hour soak validation |
| D-8 | Email double-STARTTLS class of transport fragility | Low (fixed) | One-line `start_tls=False` fix applied + delivered live; broader transport-matrix tests absent | Add SMTP transport-config regression tests (465 vs 587) |

## Notes

- D-8's defect is **already fixed and live-validated** in v1.1.0; the residual debt is test coverage
  for the transport matrix, not the bug itself.
- None of D-1…D-7 block Pilot operation; collectively they define the Production Ready gate (see
  `v1.2-planning-charter.md` §6).
- This backlog is the **sole** authorized seed for the v1.2 roadmap — no items beyond observed
  evidence.
