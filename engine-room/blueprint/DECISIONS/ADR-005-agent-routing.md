# ADR-005: Agent Routing — Rule-Based Deterministic Routing

Date: 2026-06-19
Status: Accepted (Per Documentation)

---

## Context

Nexus coordinates multiple specialized agents:
- Research Agent
- Planning Agent
- Execution Agent
- Communication Agent
- Memory Agent

Routing decisions determine which agent handles a given request.

---

## Decision

**Agent routing must be rule-based and deterministic.**

LLM-dependent routing is explicitly forbidden (Constraint 9).

### Routing Rules

```python
class AgentRouter:
    """Deterministic, rule-based agent routing."""

    ROUTING_TABLE = {
        EventType.RESEARCH_REQUEST: AgentType.RESEARCH,
        EventType.APPROVAL_REQUEST: AgentType.APPROVAL_ENGINE,
        EventType.EXECUTION_REQUEST: AgentType.EXECUTION,
        EventType.PLAN_REQUEST: AgentType.PLANNING,
        EventType.SUMMARY_REQUEST: AgentType.COMMUNICATION,
        EventType.CONTEXT_REQUEST: AgentType.MEMORY,
    }

    def route(self, event: NexusEvent) -> AgentType:
        agent_type = self.ROUTING_TABLE.get(event.event_type)
        if agent_type is None:
            raise UnroutableEventError(f"No agent for event type: {event.event_type}")
        return agent_type
```

### Routing Principles

1. Routing is a lookup, not a decision
2. Unknown event types raise errors immediately (fail fast)
3. No LLM is consulted during routing
4. Routing table is statically defined at startup
5. Every routing decision is logged with correlation ID

### Agent Independence

- Research Agent does NOT depend on Execution Agent
- Execution Agent does NOT depend on Communication Agent
- All agents depend on Shared Memory (via Memory Manager only)
- All agents receive context assembled by Nexus Core (never raw state)

---

## Consequences

**Positive:**
- Completely predictable system behavior
- Easy to test (pure function)
- No LLM cost for routing decisions
- No routing failures due to LLM availability

**Negative:**
- New event types require explicit routing table updates
- Cannot dynamically route based on content semantics

---

## Status

Accepted — consistent with Constraint 9 and agent design docs.
