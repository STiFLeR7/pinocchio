# Research Validation

> v1.1.0 bring-up · live RSS + multi-provider LLM + persistence.

## Live run
`ResearchService.execute_research_run({"hackernews": "https://hnrss.org/frontpage"})`:

- **RSS:** live feed fetched + parsed.
- **Dedup/normalize:** items normalized.
- **LLM scoring/summary:** via the multi-provider gateway (Groq primary).
- **Persistence:** **20 findings persisted**.
- **Audit:** `research.started: 1`, `research.completed: 1`.
- **Checkpointing:** research run checkpoints recorded.

## Notes on LLM capacity
- Initial attempts hit OpenRouter **402 (no credits)**; summaries fell back (engine resilience).
- Free OpenRouter models then hit **429 (rate-limit)** → a 20-item summarization timed out.
- After adding **Groq + Zenmux** providers, completion is fast/reliable (Groq ~120 ms).

The research **collection + persistence pipeline is fully operational**; summary quality/throughput
scales with LLM capacity (now multi-provider).

## Verdict
Research engine: **Pilot Ready** (RSS → score → persist → checkpoint, audited).
