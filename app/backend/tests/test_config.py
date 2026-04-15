"""Tests for CORS_ORIGINS configuration parsing."""

import importlib

import pytest

from backend.config import CORS_ORIGINS as DEFAULT_CORS_ORIGINS


def test_default_cors_origins_includes_localhost():
    """Default CORS_ORIGINS should include localhost with FRONTEND_PORT."""
    assert "http://localhost:5173" in DEFAULT_CORS_ORIGINS


def test_default_cors_origins_includes_127():
    """Default CORS_ORIGINS should include 127.0.0.1 with FRONTEND_PORT."""
    assert "http://127.0.0.1:5173" in DEFAULT_CORS_ORIGINS


@pytest.fixture
def reload_config_with_cors(monkeypatch):
    """Patch CORS_ORIGINS env var and reload config to pick it up."""

    def _do(cors_value: str):
        monkeypatch.setenv("CORS_ORIGINS", cors_value)
        import backend.config

        importlib.reload(backend.config)
        return backend.config.CORS_ORIGINS

    yield _do
    # Reload again to restore original state
    import backend.config

    importlib.reload(backend.config)


def test_custom_single_origin(reload_config_with_cors):
    """Custom CORS_ORIGINS env var with single origin parses correctly."""
    result = reload_config_with_cors("http://localhost:9999")
    assert result == ["http://localhost:9999"]


def test_custom_multiple_origins(reload_config_with_cors):
    """Custom CORS_ORIGINS env var with multiple origins parses correctly."""
    result = reload_config_with_cors("http://localhost:9999,http://127.0.0.1:9999")
    assert result == ["http://localhost:9999", "http://127.0.0.1:9999"]


def test_whitespace_ignored(reload_config_with_cors):
    """Whitespace around origins is stripped."""
    result = reload_config_with_cors("http://localhost:9999 ,  http://127.0.0.1:9999 ")
    assert result == ["http://localhost:9999", "http://127.0.0.1:9999"]


def test_empty_cors_origins_env_var(reload_config_with_cors):
    """Empty CORS_ORIGINS env var results in empty list."""
    result = reload_config_with_cors("")
    assert result == []
