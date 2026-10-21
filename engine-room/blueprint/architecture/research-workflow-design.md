# Research Workflow Design

This document details the architectural design of the background Research Job Engine in Nexus, which automates information retrieval and updates the knowledge system.

---

## 1. Engine Architecture

The [ResearchEngine](file:///D:/nexus/nexus/intelligence/research.py) coordinates scheduled background retrieval tasks. It uses search client integrations and runs model-driven summarization checks before saving findings to persistent memory records.

```
          Cron Scheduler (APScheduler Trigger)
                        |
                        v
         +--------------+--------------+
         |       ResearchEngine        |
         +--------------+--------------+
                        |
            +-----------+-----------+
            |                       |
            v                       v
      Search API / SDK        Web Scrapers
            |                       |
            +-----------+-----------+
                        |
                        v
          OpenRouter LLM Summary Gate
                        |
                        v
           SQLite Persistence Memory
      (ResearchItemRecord / KnowledgeItemRecord)
```

---

## 2. Research Sources

The engine fetches and organizes updates across six main areas:

1. **AI News & Agent Frameworks**: Updates from langchain, crewai, langgraph, and autogen ecosystems.
2. **Model Releases**: Tracking API modifications and new open/closed model endpoints.
3. **Research Papers**: Scanning arXiv database APIs for new papers on planning, routing, and agents.
4. **OpenRouter API Updates**: Cataloging new free endpoints, token pricing drops, and fallback paths.
5. **RAG & Database Advancements**: Tracking vector databases, chunking models, and embedding optimizations.
6. **MCP Ecosystem updates**: Monitoring model context protocol servers and tools.

---

## 3. Workflow Steps

A scheduled research job follows this pipeline:

1. **Trigger**: Cron job triggers a search query for a specific topic (e.g., `"Model Context Protocol servers"`).
2. **Retrieve**: The engine invokes search APIs (e.g. Google Search API, Brave Search, or Tavily) and scans feeds.
3. **Filter**: Cleans raw HTML inputs and filters out irrelevant content.
4. **Summarize**: Prompts OpenRouter (using Llama or Gemini endpoints) to extract key findings and format them.
5. **Index & Persist**: Saves records into [ResearchItemRecord](file:///D:/nexus/nexus/memory/models.py) and [KnowledgeItemRecord](file:///D:/nexus/nexus/memory/models.py), cataloged with relevant search tags.
6. **Notify**: Raises a `RESEARCH_COMPLETED` system event to trigger briefings.
