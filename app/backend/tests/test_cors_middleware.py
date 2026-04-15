"""Integration tests for CORS middleware configuration."""

import importlib

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def reload_main_with_cors(monkeypatch):
    """Patch CORS_ORIGINS env var and reload main+config to pick it up."""

    def _do(cors_value: str):
        monkeypatch.setenv("CORS_ORIGINS", cors_value)
        import backend.config

        importlib.reload(backend.config)
        import backend.main

        importlib.reload(backend.main)
        return backend.main.app

    yield _do
    # Reload again to restore original state
    import backend.config

    importlib.reload(backend.config)
    import backend.main

    importlib.reload(backend.main)


@pytest.mark.asyncio
async def test_cors_middleware_uses_configured_origins(reload_main_with_cors):
    """CORS headers reflect CORS_ORIGINS from config, not hardcoded values."""
    app = reload_main_with_cors("http://localhost:9999,http://example.com")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:9999",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert "http://localhost:9999" in response.headers.get("Access-Control-Allow-Origin", "")


@pytest.mark.asyncio
async def test_cors_middleware_rejects_unconfigured_origin(reload_main_with_cors):
    """CORS headers do not include origins not in CORS_ORIGINS."""
    app = reload_main_with_cors("http://localhost:9999,http://example.com")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/api/health",
            headers={
                "Origin": "http://untrusted.com",
                "Access-Control-Request-Method": "GET",
            },
        )
    # Access-Control-Allow-Origin should not include untrusted.com
    allowed_origin = response.headers.get("Access-Control-Allow-Origin", "")
    assert "untrusted.com" not in allowed_origin
