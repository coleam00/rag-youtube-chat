"""
Tests for the /api/version endpoint.
"""

from importlib.metadata import PackageNotFoundError
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from backend.main import app


async def test_version_endpoint_returns_200():
    """GET /api/version returns 200 with a non-empty version field."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/version")

    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert isinstance(data["version"], str)
    assert len(data["version"]) > 0


async def test_version_endpoint_returns_503_when_package_not_found():
    """GET /api/version returns 503 when dynachat-backend package is not installed."""
    with patch("backend.main.get_version") as mock_get_version:
        mock_get_version.side_effect = PackageNotFoundError("dynachat-backend")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/version")

    assert response.status_code == 503
    assert response.json()["detail"] == "Package metadata unavailable"
