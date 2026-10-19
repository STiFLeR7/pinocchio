"""Pydantic v2 request / response schemas for the Nexus API.

Schemas are intentionally decoupled from the ORM models so the API
contract can evolve independently of the storage layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from nexus.core.types import (
    ApprovalStatus,
    Priority,
    RunnerType,
    TaskStatus,
)

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Response schema for the ``/health`` endpoint."""

    status: str
    version: str
    timestamp: datetime


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


class TaskCreate(BaseModel):
    """Request body for creating a new task."""

    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = Field(default=None)
    priority: Priority = Field(default=Priority.MEDIUM)
    runtime_type: str | None = Field(default="cli")
    runtime_id: str | None = Field(default="gemini")
    execution_profile: str | None = Field(default="default")
    runtime_policy: str | None = Field(default="approved")

    model_config = {
        "json_schema_extra": {"examples": [{"title": "Implement auth module", "priority": 3}]}
    }


class TaskUpdate(BaseModel):
    """Request body for updating an existing task."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None)
    status: TaskStatus | None = Field(default=None)
    priority: Priority | None = Field(default=None)
    is_archived: bool | None = Field(default=None)
    runtime_type: str | None = Field(default=None)
    runtime_id: str | None = Field(default=None)
    execution_profile: str | None = Field(default=None)
    runtime_policy: str | None = Field(default=None)


class TaskResponse(BaseModel):
    """Response schema for a task entity."""

    id: uuid.UUID
    title: str
    description: str | None
    status: TaskStatus
    priority: int
    runtime_type: str | None
    runtime_id: str | None
    execution_profile: str | None
    runtime_policy: str | None
    created_at: datetime
    updated_at: datetime
    is_archived: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------


class ApprovalCreate(BaseModel):
    """Request body for requesting a new approval."""

    task_id: uuid.UUID
    expires_at: datetime | None = Field(default=None)

    model_config = {
        "json_schema_extra": {"examples": [{"task_id": "550e8400-e29b-41d4-a716-446655440000"}]}
    }


class ApprovalResponse(BaseModel):
    """Response schema for an approval entity."""

    id: uuid.UUID
    task_id: uuid.UUID
    status: ApprovalStatus
    requested_at: datetime
    decided_at: datetime | None
    decided_by: str | None
    expires_at: datetime | None
    decision_reason: str | None
    created_at: datetime
    updated_at: datetime
    is_archived: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Executions
# ---------------------------------------------------------------------------


class ExecutionCreate(BaseModel):
    """Request body for initiating a new execution."""

    task_id: uuid.UUID
    approval_id: uuid.UUID | None = Field(default=None)
    runner: RunnerType
    repository: str | None = Field(default=None)
    timeout_threshold: int | None = Field(default=None, ge=60, le=7200)


class ExecutionResponse(BaseModel):
    """Response schema for an execution entity."""

    id: uuid.UUID
    task_id: uuid.UUID
    approval_id: uuid.UUID | None
    runner: str
    repository: str | None
    started_at: datetime | None
    last_heartbeat: datetime | None
    timeout_threshold: int | None
    completed_at: datetime | None
    exit_status: str | None
    logs: str | None
    result: str | None
    created_at: datetime
    updated_at: datetime
    is_archived: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


class AuditLogEntry(BaseModel):
    """Response schema for an audit log record."""

    id: uuid.UUID
    event_type: str
    entity_type: str
    entity_id: uuid.UUID | None
    data: dict[str, Any] | None
    correlation_id: uuid.UUID | None
    component: str | None
    actor: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Context Frames
# ---------------------------------------------------------------------------


class ContextFrame(BaseModel):
    """Derived ephemeral prompt context frame compiled during turn execution."""

    workflow_id: uuid.UUID
    messages: list[dict[str, Any]] = Field(default_factory=list)
    model: str
    thinking_level: int | None = Field(default=None)
    active_tools: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Research Findings (AP-306)
# ---------------------------------------------------------------------------


class ResearchFindingCreate(BaseModel):
    """Request body/creation payload for a research finding."""

    source: str | None = Field(default=None, max_length=500)
    title: str = Field(..., min_length=1, max_length=500)
    url: str | None = Field(default=None, max_length=1000)
    summary: str | None = Field(default=None)
    tags: list[str] | None = Field(default_factory=list)
    importance_score: int | None = Field(default=0)
    published_at: datetime | None = Field(default=None)


class ResearchFindingResponse(BaseModel):
    """Response schema for a research finding."""

    id: uuid.UUID
    source: str | None
    title: str
    url: str | None
    summary: str | None
    tags: list[str] | None
    importance_score: int | None
    discovered_at: datetime
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    is_archived: bool

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Briefings (AP-307)
# ---------------------------------------------------------------------------


class BriefingCreate(BaseModel):
    """Request/creation payload for a briefing record."""

    briefing_type: str = Field(..., min_length=1, max_length=100)
    delivery_channels: list[str] | None = Field(default_factory=list)
    content_hash: str = Field(..., max_length=64)
    finding_count: int = Field(default=0)
    status: str = Field(default="pending", max_length=50)
    summary: str = Field(...)


class BriefingResponse(BaseModel):
    """Response schema for a briefing record."""

    id: uuid.UUID
    briefing_type: str
    generated_at: datetime
    delivery_channels: list[str] | None
    content_hash: str
    finding_count: int
    status: str
    summary: str
    created_at: datetime
    updated_at: datetime
    is_archived: bool

    model_config = {"from_attributes": True}
