# Daily Briefing Design

This document details the architectural design for the Nexus Daily Briefing Engine, which compiles system logs, pending actions, and research findings into summaries distributed to operators.

---

## 1. Briefing Flow

The [DailyBriefingEngine](file:///D:/nexus/nexus/intelligence/briefing.py) executes as a scheduled job at the end of each day or on demand via operator slash commands.

```
                  Trigger (Cron / Command)
                             |
                             v
           Retrieve Records from SQLite Memory
     (Open Tasks, Pending Approvals, Failures, Research)
                             |
                             v
                 OpenRouter LLM Synthesis
                             |
                             v
             Jinja2 Template Formatting Loop
                             |
            +----------------+----------------+
            |                                 |
            v                                 v
   Discord webhook API                 SMTP Mail Service
   (#briefings channel)                 (aiosmtplib mail)
```

---

## 2. Information Retrieval Scope

The briefing engine queries the database to gather details across five areas:

* **Open Tasks**: Outstanding tasks that are in `QUEUED`, `ACTIVE`, or `BLOCKED` states.
* **Pending Approvals**: Verification requests in [ApprovalRecord](file:///D:/nexus/nexus/memory/models.py) waiting for owner approval.
* **Failed Executions**: Command executions that failed, tracking error details and exit codes.
* **Research Findings**: Summaries of search results saved in `ResearchItemRecord` over the last 24 hours.
* **System Health**: Statistics on system health and database operations.

---

## 3. Templating & Presentation

Briefings are formatted using Jinja2 templates to tailor outputs for different channels:

### Discord Format
* **Output**: Discord Embed layout.
* **Style**: Organized with markdown fields, color-coded status sections (e.g., green for healthy, red for failures), and direct user tags for pending approvals.

### Email Format
* **Output**: HTML template.
* **Style**: A structured email message containing details on recent execution histories and research findings.

---

## 4. Routing Service Integrations

* **Discord**: Sends payload blocks to the `#summaries` or `#alerts` channels using [DiscordService.post_message](file:///D:/nexus/nexus/communication/discord/service.py#L55-L74).
* **Email Gateway**: Connects to SMTP hosts using `aiosmtplib` to send reports to configured email endpoints.
