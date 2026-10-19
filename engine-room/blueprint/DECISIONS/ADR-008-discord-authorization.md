# ADR-008: Discord Authorization — User ID Enforcement

Date: 2026-06-19
Status: Accepted
Decided By: Hill Patel

---

## Decision

All privileged Discord actions must be authorized by Discord User ID.

Only users in the `OWNER_DISCORD_IDS` configuration may:
- Approve execution
- Reject execution
- Override workflows
- Execute privileged actions
- Interact with approval buttons

---

## Configuration

```yaml
discord:
  owner_ids:
    - ${OWNER_DISCORD_ID}  # Primary owner
  # Future: RBAC list
```

---

## Implementation

```python
class DiscordAuthGuard:
    """Enforces Discord User ID authorization."""

    def __init__(self, owner_ids: list[int]) -> None:
        self._owner_ids = set(owner_ids)

    def is_authorized(self, user_id: int) -> bool:
        return user_id in self._owner_ids

    def require_authorized(self, user_id: int) -> None:
        if not self.is_authorized(user_id):
            raise UnauthorizedActionError(
                f"User {user_id} is not authorized to perform this action"
            )
```

All approval button interactions must pass through `DiscordAuthGuard` before processing.

Unauthorized attempts must:
1. Be logged with user ID and action attempted
2. Generate an audit event
3. Silently discard (no confirmation message to unauthorized user)

---

## Future

RBAC (Role-Based Access Control):
- Multiple users with different permission levels
- Role assignment via configuration

Current MVP: Single-user governance only.

---

## Status

Accepted — Owner approved 2026-06-19.
