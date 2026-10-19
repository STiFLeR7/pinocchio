# ADR-007: Email Provider — Gmail SMTP with Abstraction Layer

Date: 2026-06-19
Status: Accepted
Decided By: Hill Patel

---

## Decision

**Gmail SMTP** is the MVP email provider.

**Mandatory:** An `EmailProvider` abstraction must be created from day one to allow migration without changing business logic.

---

## Rationale

- Already available in `.env`
- Zero additional cost
- Fastest path to MVP

---

## Migration Path

```
SMTP Interface (abstraction)
    │
    ▼
Gmail SMTP          ← MVP
    │
    ▼
Resend              ← Next
    │
    ▼
SES / Postmark      ← Future
```

---

## Implementation Contract

```python
class EmailProvider(Protocol):
    """Abstract email provider interface."""
    async def send(
        self,
        to: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
    ) -> EmailSendResult: ...


class GmailSMTPProvider:
    """Gmail SMTP implementation."""
    ...


class ResendProvider:
    """Resend API implementation (future)."""
    ...
```

The `EmailService` depends only on `EmailProvider`.

Swapping providers requires only changing the provider injection — no business logic changes.

---

## Required Configuration

```yaml
email:
  provider: gmail_smtp
  smtp_host: smtp.gmail.com
  smtp_port: 587
  username: ${NOTIFY_EMAIL_FROM}
  password: ${NOTIFY_SMTP_PASSWORD}
  from_address: ${NOTIFY_EMAIL_FROM}
  to_address: hillaniljppatel@gmail.com
```

---

## Status

Accepted — Owner approved 2026-06-19.
