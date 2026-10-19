# Hermes Agent — Evaluation Report

Status: 🔲 Not Started
Priority: High (Must complete before Phase 4)
Repository: https://github.com/nousresearch/hermes-agent
Local availability: `hermes` command available in terminal

---

## Background

Hermes Agent is already installed locally and available as `hermes` from PowerShell and Command Prompt.

Nexus docs indicate Hermes should be evaluated as a potential execution runtime before Phase 4 (Execution Runtime).

**Critical Constraint:**
Hermes must never own:
- Approvals
- Memory
- Governance
- Task Authority
- Execution Authorization

These remain inside Nexus Core.

## Evaluation Questions

### CLI Interface
- [ ] What is the CLI signature? (`hermes --help`)
- [ ] How are tasks/prompts provided?
- [ ] What output format does Hermes produce?
- [ ] Does Hermes support structured input (JSON, YAML)?

### Execution Model
- [ ] Is Hermes synchronous or async?
- [ ] Can Hermes be launched as a subprocess?
- [ ] What is the startup/shutdown time?
- [ ] Can Hermes run in headless/non-interactive mode?

### Tool Calling
- [ ] What tools does Hermes support?
- [ ] Can it execute file operations?
- [ ] Can it execute git operations?
- [ ] Can it execute terminal commands?

### Configuration
- [ ] How is Hermes configured?
- [ ] What models does it support?
- [ ] Can it be pointed at OpenRouter?

### State Model
- [ ] Does Hermes maintain session state?
- [ ] Does it have memory between runs?
- [ ] Can Nexus retrieve Hermes session output?

### Logging
- [ ] Does Hermes emit structured logs?
- [ ] Can Nexus capture Hermes stdout/stderr?

### Extensibility
- [ ] Can new tools be added?
- [ ] Can it be called programmatically?

### Failure Recovery
- [ ] What happens when a Hermes task fails?
- [ ] Does it retry internally?
- [ ] Does it produce exit codes?

---

## Findings

*(To be filled after evaluation)*

### CLI Behavior

```
# Run: hermes --help
# Paste output here
```

### Execution Contract

*(TBD)*

### Strengths

*(TBD)*

### Weaknesses

*(TBD)*

---

## Decision

*(To be filled after evaluation)*

**Options:**

| Option | Description |
|---|---|
| A — Primary Runtime | Use Hermes as the main execution agent |
| B — Secondary Runtime | Use alongside Gemini CLI and Claude Code |
| C — Specialized Runtime | Use for specific task types only |
| D — Rejected | Not suitable; use Gemini CLI and Claude Code only |

**Chosen Option:** TBD

**Justification:** TBD

---

## Action Required

1. Run `hermes --help` and document the interface
2. Run a simple test task
3. Test structured input/output
4. Evaluate subprocess controllability
5. Update this document
6. Record decision in ADR (to be created)
