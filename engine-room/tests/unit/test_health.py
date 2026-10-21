"""Unit tests for the health check and status API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_health_endpoint_returns_200(client: AsyncClient) -> None:
    """Verify that GET /health returns 200 HTTP status code."""
    response = await client.get("/health")
    assert response.status_code == 200


async def test_health_response_structure(client: AsyncClient) -> None:
    """Verify that GET /health returns the correct JSON response structure."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "timestamp" in data


async def test_health_status_is_healthy(client: AsyncClient) -> None:
    """Verify that GET /health returns 'healthy' status."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
