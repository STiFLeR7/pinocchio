# ADR-009: Approval Expiration Policy

Date: 2026-06-19
Status: Accepted
Decided By: Hill Patel

---

## Decision

Approval requests expire after **24 hours**.

Expiration does **NOT** auto-reject.

---

## Expiration Flow

```
ApprovalRequested
       │
       ▼
   [Pending]
       │
  (24h elapsed)
       │
       ▼
   [Expired]
       │
       ├── Mark as Expired in Memory
       ├── Send notification via Discord + Email
       └── Move to review queue (re-approval required)
```

---

## Rationale

Auto-rejection was rejected because:
- Approval may have been missed due to Discord outage
- User may have been temporarily unavailable
- Losing valid work due to expiration is unacceptable

Instead: expire and notify, require conscious re-approval decision.

---

## State Machine

```python
class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
```

Valid transitions:
- `PENDING` → `APPROVED` (user action)
- `PENDING` → `REJECTED` (user action)
- `PENDING` → `EXPIRED` (24h scheduler)
- `PENDING` → `CANCELLED` (system action)
- `EXPIRED` → `PENDING` (re-request, new approval record created)

No other transitions are valid.

---

## Scheduler Job

```python
# Runs every hour to catch expired approvals
@scheduler.scheduled_job("interval", hours=1)
async def check_approval_expirations():
    expired = await approval_repo.find_expired_pending()
    for approval in expired:
        await approval_engine.expire(approval)
```

---

## Notification Content

When approval expires:

```
⏰ Approval Expired

Task: [task title]
Approval ID: [id]
Requested: [timestamp]
Expired: [timestamp]
Action Required: Re-request approval to proceed.
```

---

## Status

Accepted — Owner approved 2026-06-19.
