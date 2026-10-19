"""AP-306 Research Engine Subsystem.

Implements provider abstractions, RSS feed crawling, content normalization,
deduplication, LLM summarization/importance scoring, and checkpoint recovery.
"""

from __future__ import annotations

import contextlib
import email.utils
import json
import uuid
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx
import structlog
from sqlalchemy import select

from nexus.core.events import NexusEvent
from nexus.core.types import EventType
from nexus.memory.models import ResearchFindingRecord

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from nexus.intelligence.openrouter import OpenRouterClient
    from nexus.memory.service import MemoryService

logger = structlog.get_logger("nexus.intelligence.research")


def _find_child_by_local_name(parent: ET.Element, name: str) -> ET.Element | None:
    """Namespace-agnostic search for a child element by local name."""
    name_lower = name.lower()
    # Check direct children first
    for child in parent:
        local_name = child.tag.split("}")[-1].lower()
        if local_name == name_lower:
            return child
    # Fallback to recursive search
    for child in parent.iter():
        if child == parent:
            continue
        local_name = child.tag.split("}")[-1].lower()
        if local_name == name_lower:
            return child
    return None


def _serialize_state(state: dict[str, Any]) -> dict[str, Any]:
    """Helper to recursively serialize datetime/UUID values in state dict to JSON safe strings."""
    return {k: _serialize_val(v) for k, v in state.items()}


def _serialize_val(val: Any) -> Any:
    """Helper to convert values to JSON-safe types."""
    if isinstance(val, datetime):
        return val.isoformat()
    elif isinstance(val, uuid.UUID):
        return str(val)
    elif isinstance(val, dict):
        return _serialize_state(val)
    elif isinstance(val, list):
        return [_serialize_val(item) for item in val]
    return val


class ResearchProvider(ABC):
    """Abstract base class defining the contract for technical research data collectors."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier for the provider."""
        pass

    @abstractmethod
    async def collect_sources(self, feed_name: str, feed_url: str) -> list[dict[str, Any]]:
        """Fetch raw articles or postings from the given feed configuration."""
        pass


class RSSProvider(ResearchProvider):
    """Generic feed reader supporting RSS 2.0 and Atom XML schemas."""

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        return "rss_provider"

    async def collect_sources(self, feed_name: str, feed_url: str) -> list[dict[str, Any]]:
        """Fetch XML feed content from feed_url and extract raw entries."""
        logger.info("fetching_feed", feed_name=feed_name, url=feed_url)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(feed_url)
                res.raise_for_status()
                xml_content = res.text
        except Exception as e:
            logger.error("failed_fetching_feed", feed_name=feed_name, url=feed_url, error=str(e))
            return []

        try:
            return self._parse_feed_xml(xml_content, feed_name)
        except Exception as e:
            logger.error("failed_parsing_feed_xml", feed_name=feed_name, error=str(e))
            return []

    def _parse_feed_xml(self, xml_content: str, feed_name: str) -> list[dict[str, Any]]:
        """Parse RSS/Atom XML text to standard dict format."""
        root = ET.fromstring(xml_content.encode("utf-8", errors="ignore"))
        findings: list[dict[str, Any]] = []

        # Find elements ending with item (RSS) or entry (Atom)
        for el in root.iter():
            tag_local = el.tag.split("}")[-1].lower()
            if tag_local == "item":
                # Parse RSS Item
                title_el = _find_child_by_local_name(el, "title")
                link_el = _find_child_by_local_name(el, "link")
                desc_el = _find_child_by_local_name(el, "description")
                pub_el = _find_child_by_local_name(el, "pubDate")

                title = title_el.text.strip() if title_el is not None and title_el.text else ""
                url = link_el.text.strip() if link_el is not None and link_el.text else ""
                summary = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

                published_at = None
                if pub_el is not None and pub_el.text:
                    with contextlib.suppress(Exception):
                        published_at = email.utils.parsedate_to_datetime(pub_el.text.strip())

                findings.append({
                    "source": feed_name,
                    "title": title,
                    "url": url,
                    "summary": summary,
                    "published_at": published_at,
                })

            elif tag_local == "entry":
                # Parse Atom Entry
                title_el = _find_child_by_local_name(el, "title")

                # Check for link href
                url = ""
                links = []
                for child in el:
                    if child.tag.split("}")[-1].lower() == "link":
                        links.append(child)
                for link_item in links:
                    href = link_item.attrib.get("href")
                    if href:
                        url = href.strip()
                        break

                summary_el = _find_child_by_local_name(el, "summary")
                if summary_el is None:
                    summary_el = _find_child_by_local_name(el, "content")

                pub_el = _find_child_by_local_name(el, "published")
                if pub_el is None:
                    pub_el = _find_child_by_local_name(el, "updated")

                title = title_el.text.strip() if title_el is not None and title_el.text else ""
                summary = (
                    summary_el.text.strip()
                    if summary_el is not None and summary_el.text
                    else ""
                )

                published_at = None
                if pub_el is not None and pub_el.text:
                    try:
                        date_str = pub_el.text.strip()
                        if date_str.endswith("Z"):
                            date_str = date_str[:-1] + "+00:00"
                        published_at = datetime.fromisoformat(date_str)
                    except Exception:
                        pass

                findings.append({
                    "source": feed_name,
                    "title": title,
                    "url": url,
                    "summary": summary,
                    "published_at": published_at,
                })

        return findings


class ResearchService:
    """Orchestrates autonomous technical topic research cycles."""

    def __init__(
        self,
        db_session: AsyncSession,
        openrouter_client: OpenRouterClient,
        memory_service: MemoryService,
    ) -> None:
        self.session = db_session
        self.openrouter = openrouter_client
        self.memory_service = memory_service
        self._providers: dict[str, ResearchProvider] = {}
        # Register default provider
        self.register_provider(RSSProvider())

    def register_provider(self, provider: ResearchProvider) -> None:
        """Register research source collector."""
        self._providers[provider.provider_name] = provider

    async def execute_research_run(
        self,
        feeds: dict[str, str],
        workflow_id: uuid.UUID | None = None,
    ) -> list[uuid.UUID]:
        """Conduct autonomous topic research.

        Processes raw feed inputs, normalizes, deduplicates, calls LLM for summaries,
        and persists output findings to database. Supports checkpoint recovery.
        """
        run_id = workflow_id or uuid.uuid4()

        # Log start event
        start_event = NexusEvent(
            event_type=EventType.RESEARCH_STARTED,
            entity_type="research_run",
            entity_id=run_id,
            data={"run_id": str(run_id), "feeds_count": len(feeds)},
            source="research_engine",
        )
        await self.memory_service.log_event(start_event)

        logger.info("starting_research_run", run_id=str(run_id))

        # Initialize Checkpoint state
        checkpoint_state: dict[str, Any] = {
            "run_id": str(run_id),
            "step": "initialized",
            "findings": [],
            "feeds": feeds,
        }
        await self.memory_service.create_checkpoint(
            run_id, "initialized", _serialize_state(checkpoint_state)
        )

        try:
            # 1. Fetch from RSS sources
            findings_raw: list[dict[str, Any]] = []
            rss_prov = self._providers["rss_provider"]

            for feed_name, feed_url in feeds.items():
                items = await rss_prov.collect_sources(feed_name, feed_url)
                findings_raw.extend(items)

            # Checkpoint: Collected
            checkpoint_state["step"] = "collected"
            checkpoint_state["findings"] = findings_raw
            await self.memory_service.create_checkpoint(
                run_id, "collected", _serialize_state(checkpoint_state)
            )

            # 2. Deduplicate
            non_duplicate_findings = await self._deduplicate_findings(findings_raw)
            checkpoint_state["step"] = "deduplicated"
            checkpoint_state["findings"] = non_duplicate_findings
            await self.memory_service.create_checkpoint(
                run_id, "deduplicated", _serialize_state(checkpoint_state)
            )

            if not non_duplicate_findings:
                logger.info("no_new_findings_to_process", run_id=str(run_id))
                return []

            # 3. Summarize via OpenRouter
            final_findings: list[dict[str, Any]] = []
            for idx, finding in enumerate(non_duplicate_findings):
                logger.info(
                    "summarizing_finding",
                    index=idx,
                    total=len(non_duplicate_findings),
                    title=finding["title"],
                )
                summarized = await self._summarize_finding(finding)
                final_findings.append(summarized)

                # Intermediary Checkpoint to prevent re-processing on timeouts
                checkpoint_state["findings"] = final_findings + non_duplicate_findings[idx + 1 :]
                checkpoint_state["summarized_count"] = len(final_findings)
                await self.memory_service.create_checkpoint(
                    run_id, "summarizing", _serialize_state(checkpoint_state)
                )

            # 4. Persist to DB
            persisted_ids = []
            for item in final_findings:
                # Ensure published_at is timezone-aware if present
                pub_at = item.get("published_at")
                if pub_at and isinstance(pub_at, str):
                    pub_at = datetime.fromisoformat(pub_at)

                rec = ResearchFindingRecord(
                    id=uuid.uuid4(),
                    source=item["source"],
                    title=item["title"],
                    url=item["url"],
                    summary=item["summary"],
                    tags=item["tags"],
                    importance_score=item["importance_score"],
                    published_at=pub_at,
                    discovered_at=datetime.now(UTC),
                )
                self.session.add(rec)
                persisted_ids.append(rec.id)

            await self.session.flush()

            # Checkpoint: Completed
            checkpoint_state["step"] = "completed"
            checkpoint_state["persisted_ids"] = [str(pid) for pid in persisted_ids]
            await self.memory_service.create_checkpoint(
                run_id, "completed", _serialize_state(checkpoint_state)
            )

            # Emit success audit event
            success_event = NexusEvent(
                event_type=EventType.RESEARCH_COMPLETED,
                entity_type="research_run",
                entity_id=run_id,
                data={
                    "run_id": str(run_id),
                    "persisted_findings_count": len(persisted_ids),
                    "finding_ids": [str(pid) for pid in persisted_ids],
                },
                source="research_engine",
            )
            await self.memory_service.log_event(success_event)

            logger.info("research_run_successful", run_id=str(run_id), count=len(persisted_ids))
            return persisted_ids

        except Exception as e:
            logger.error("research_run_failed", run_id=str(run_id), error=str(e))
            # Log failure audit event
            failed_event = NexusEvent(
                event_type=EventType.RESEARCH_FAILED,
                entity_type="research_run",
                entity_id=run_id,
                data={"run_id": str(run_id), "error": str(e)},
                source="research_engine",
            )
            await self.memory_service.log_event(failed_event)
            raise

    async def resume_research_run(self, workflow_id: uuid.UUID) -> list[uuid.UUID]:
        """Resume a checkpointed research execution loop after failure."""
        state = await self.memory_service.restore_checkpoint(workflow_id)
        if not state:
            raise ValueError(f"No checkpoint state found for research run: {workflow_id}")

        step = state.get("step")
        logger.info("resuming_research_run", run_id=str(workflow_id), step=step)

        # Reconstruct timestamp datetimes for serialized dates
        findings = state.get("findings", [])
        for f in findings:
            if f.get("published_at") and isinstance(f["published_at"], str):
                f["published_at"] = datetime.fromisoformat(f["published_at"])

        # Emit resume log
        resume_event = NexusEvent(
            event_type=EventType.WORKFLOW_RESUMED,
            entity_type="research_run",
            entity_id=workflow_id,
            data={"run_id": str(workflow_id), "step": step},
            source="research_engine",
        )
        await self.memory_service.log_event(resume_event)

        if step == "initialized":
            # Restart from scratch
            return await self.execute_research_run(state["feeds"], workflow_id)

        elif step == "collected":
            # Collected state has all raw findings. Proceed to deduplication.
            non_duplicates = await self._deduplicate_findings(findings)
            state["step"] = "deduplicated"
            state["findings"] = non_duplicates
            await self.memory_service.create_checkpoint(
                workflow_id, "deduplicated", _serialize_state(state)
            )
            return await self._process_from_deduplicated(workflow_id, state)

        elif step == "deduplicated":
            return await self._process_from_deduplicated(workflow_id, state)

        elif step == "summarizing":
            # Resume summarization loop
            # state['findings'] has partial summarized findings and remaining raw findings
            summarized_count = state.get("summarized_count", 0)
            completed_findings = findings[:summarized_count]
            remaining_findings = findings[summarized_count:]

            for idx, finding in enumerate(remaining_findings):
                logger.info(
                    "summarizing_finding_on_resume",
                    index=summarized_count + idx,
                    total=len(findings),
                    title=finding["title"],
                )
                summarized = await self._summarize_finding(finding)
                completed_findings.append(summarized)

                # Checkpoint progress
                state["findings"] = completed_findings + remaining_findings[idx + 1 :]
                state["summarized_count"] = len(completed_findings)
                await self.memory_service.create_checkpoint(
                    workflow_id, "summarizing", _serialize_state(state)
                )

            # Persist
            persisted_ids = []
            for item in completed_findings:
                pub_at = item.get("published_at")
                if pub_at and isinstance(pub_at, str):
                    pub_at = datetime.fromisoformat(pub_at)

                rec = ResearchFindingRecord(
                    id=uuid.uuid4(),
                    source=item["source"],
                    title=item["title"],
                    url=item["url"],
                    summary=item["summary"],
                    tags=item["tags"],
                    importance_score=item["importance_score"],
                    published_at=pub_at,
                    discovered_at=datetime.now(UTC),
                )
                self.session.add(rec)
                persisted_ids.append(rec.id)

            await self.session.flush()

            # Complete checkpoint
            state["step"] = "completed"
            state["persisted_ids"] = [str(pid) for pid in persisted_ids]
            await self.memory_service.create_checkpoint(
                workflow_id, "completed", _serialize_state(state)
            )

            success_event = NexusEvent(
                event_type=EventType.RESEARCH_COMPLETED,
                entity_type="research_run",
                entity_id=workflow_id,
                data={
                    "run_id": str(workflow_id),
                    "persisted_findings_count": len(persisted_ids),
                },
                source="research_engine",
            )
            await self.memory_service.log_event(success_event)
            return persisted_ids

        elif step == "completed":
            # Already done, return persisted IDs
            pids = state.get("persisted_ids", [])
            return [uuid.UUID(pid) for pid in pids]

        return []

    async def _process_from_deduplicated(
        self, workflow_id: uuid.UUID, state: dict[str, Any]
    ) -> list[uuid.UUID]:
        """Internal helper to process findings starting from deduplicated checkpoint."""
        findings = state["findings"]
        final_findings = []
        for idx, finding in enumerate(findings):
            logger.info(
                "summarizing_finding",
                index=idx,
                total=len(findings),
                title=finding["title"],
            )
            summarized = await self._summarize_finding(finding)
            final_findings.append(summarized)

            # Checkpoint
            state["step"] = "summarizing"
            state["findings"] = final_findings + findings[idx + 1 :]
            state["summarized_count"] = len(final_findings)
            await self.memory_service.create_checkpoint(
                workflow_id, "summarizing", _serialize_state(state)
            )

        # Persist
        persisted_ids = []
        for item in final_findings:
            pub_at = item.get("published_at")
            if pub_at and isinstance(pub_at, str):
                pub_at = datetime.fromisoformat(pub_at)

            rec = ResearchFindingRecord(
                id=uuid.uuid4(),
                source=item["source"],
                title=item["title"],
                url=item["url"],
                summary=item["summary"],
                tags=item["tags"],
                importance_score=item["importance_score"],
                published_at=pub_at,
                discovered_at=datetime.now(UTC),
            )
            self.session.add(rec)
            persisted_ids.append(rec.id)

        await self.session.flush()

        state["step"] = "completed"
        state["persisted_ids"] = [str(pid) for pid in persisted_ids]
        await self.memory_service.create_checkpoint(
            workflow_id, "completed", _serialize_state(state)
        )

        success_event = NexusEvent(
            event_type=EventType.RESEARCH_COMPLETED,
            entity_type="research_run",
            entity_id=workflow_id,
            data={
                "run_id": str(workflow_id),
                "persisted_findings_count": len(persisted_ids),
            },
            source="research_engine",
        )
        await self.memory_service.log_event(success_event)
        return persisted_ids

    async def _deduplicate_findings(self, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter out findings where URL (or title) is already recorded in the database."""
        non_duplicates: list[dict[str, Any]] = []
        for f in findings:
            if not f.get("url"):
                # If no URL, check by title
                stmt = select(ResearchFindingRecord).where(
                    ResearchFindingRecord.title == f["title"]
                )
            else:
                stmt = select(ResearchFindingRecord).where(ResearchFindingRecord.url == f["url"])

            res = await self.session.execute(stmt)
            existing = res.scalar_one_or_none()
            if not existing:
                non_duplicates.append(f)
        return non_duplicates

    async def _summarize_finding(self, finding: dict[str, Any]) -> dict[str, Any]:
        """Enrich a finding with an LLM-compiled summary, importance rating, and tags."""
        prompt = (
            f"You are the Nexus Research Auditor. Analyze this finding from feed source "
            f"'{finding['source']}':\n\n"
            f"Title: {finding['title']}\n"
            f"Raw Snippet/Content: {finding['summary'] or 'No summary provided.'}\n\n"
            "Produce a structured JSON response with the following keys:\n"
            "- summary: A concise Markdown bulleted summary (under 100 words).\n"
            "- importance_score: An integer from 1 to 5 indicating relevance/importance "
            "to AI agents, LLM infrastructure, and software developers "
            "(1 = low, 5 = ground-breaking/critical).\n"
            "- tags: A list of 2 to 5 relevant technical tags (lowercase strings).\n\n"
            "Response MUST be valid JSON only. Do not wrap in markdown code fences "
            "or add greeting/signature text."
        )
        system_prompt = "You are a precise, technical AI analyst."

        try:
            res_text = await self.openrouter.complete(prompt, system_prompt)
            data = self._extract_json(res_text)

            # Enrich original finding
            finding["summary"] = data.get("summary") or finding["summary"]
            finding["importance_score"] = int(data.get("importance_score", 0))
            finding["tags"] = data.get("tags") or []
        except Exception as e:
            logger.warning(
                "llm_summarization_failed_using_fallback",
                error=str(e),
                title=finding["title"],
            )
            # Fallback values
            finding["importance_score"] = 0
            finding["tags"] = ["research", finding["source"].lower()]

        # Convert date to string format for serialization in checkpoints
        if finding.get("published_at") and isinstance(finding["published_at"], datetime):
            finding["published_at"] = finding["published_at"].isoformat()

        return finding

    def _extract_json(self, text: str) -> dict[str, Any]:
        """Robust parser to extract JSON blocks from responses with optional markdown fences."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            # strip start fence
            lines = cleaned.split("\n")
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].endswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        return dict(json.loads(cleaned))
