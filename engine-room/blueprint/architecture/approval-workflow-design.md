# Approval Workflow Architecture & Gating Design

This document details the mechanics of the manual governance gates protecting execution pipelines in Nexus.

---

## 1. Approval State Machine

```
                      ┌───────────────┐
                      │    PENDING    │
                      └──────┬┬───────┘
                             ││
            ┌────────────────┘└────────────────┐
            ▼                                  ▼
      ┌───────────┐                      ┌───────────┐
      │ APPROVED  │                      │ REJECTED  │
      └───────────┘                      └───────────┘
```

The approval record follows a strict enum-guided lifecycle:
* **PENDING**: Initial state. A Discord embed with interactive buttons is published. The parent task is transitioned to `BLOCKED`.
* **APPROVED**: Transitioned when an authorized `owner_id` approves the card. The parent task moves to `ACTIVE` and triggers the execution run.
* **REJECTED**: Transitioned when the owner rejects the card. The parent task is set to `CANCELLED`.
* **EXPIRED**: Transferred by the background sweep if no action is taken within the default 24-hour window. The parent task is updated to `CANCELLED`.

---

## 2. Security & Verification Gate

Every approval button click invokes a gate evaluation procedure:
```python
def check_authority(deciding_user_id: int, owner_ids: list[int]) -> bool:
    return deciding_user_id in owner_ids
```
1. The Discord Bot intercepts the interaction payload.
2. The user ID is retrieved from the interaction context (`interaction.user.id`).
3. If the ID matches an element in the settings list `settings.discord.owner_ids`, the action is evaluated.
4. If not, the bot responds with an ephemeral error message: `"Unauthorized: Only designated owners can authorize task execution."`

---

## 3. Expiration Sweeper Mechanism

A background task runs periodically (e.g. every 60 seconds) to identify stale approvals:
1. Selects all `ApprovalRecord` rows where `status == "pending"` and `expires_at < utcnow()`.
2. Updates `ApprovalRecord.status` to `EXPIRED`.
3. Sets `TaskRecord.status` to `CANCELLED` (or `FAILED` as configured) to release the workflow envelope.
4. Emits `APPROVAL_EXPIRED` system event.
5. Updates the original Discord embed to a greyed-out expired state.

---

## 4. Concurrency & Gating Safeguard

To prevent double-approvals or race conditions where two operators click buttons simultaneously:
* The transaction to evaluate approval applies a `SELECT FOR UPDATE` (or database-level lock equivalent) on the `ApprovalRecord` row.
* If the row status is not `pending`, the transaction immediately rolls back and returns an error to the user interface.
* This ensures that only the very first interaction succeeds.
