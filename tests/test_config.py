"""Configuration behavior tests.

Covers API base URL resolution, safe database URL masking (no password leaks),
and that user-facing hosted/local mode messages are well-formed strings.
No external services are contacted.
"""

import importlib

import pytest

DEFAULT_LOCAL_API_URL = "http://127.0.0.1:8001"


def _import_dashboard():
    """Import the dashboard module, skipping if Streamlit page setup fails."""
    try:
        return importlib.import_module("dashboard.app")
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"dashboard.app could not be imported in test context: {exc}")


def test_mask_database_url_hides_password() -> None:
    from backend.database import mask_database_url

    raw = "postgresql://crisis_user:SuperSecret123@localhost:5432/crisisdb"
    masked = mask_database_url(raw)

    assert "SuperSecret123" not in masked
    assert "***" in masked
    assert "crisis_user" in masked
    assert "localhost:5432/crisisdb" in masked


def test_mask_database_url_is_noop_without_credentials() -> None:
    from backend.database import mask_database_url

    plain = "postgresql://localhost:5432/crisisdb"
    assert mask_database_url(plain) == plain


def test_get_database_url_does_not_leak_password_in_repr() -> None:
    from backend.database import get_database_url, mask_database_url

    url = get_database_url()
    assert isinstance(url, str) and url

    masked = mask_database_url(url)
    if ":" in url.split("://", 1)[-1].split("@")[0]:
        # A password component exists; confirm it is masked away.
        secret = url.split("://", 1)[1].split("@")[0].split(":", 1)[1]
        if secret:
            assert secret not in masked


def test_api_base_url_default_when_env_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("API_BASE_URL", raising=False)
    app = _import_dashboard()
    assert app.get_api_base() == DEFAULT_LOCAL_API_URL


def test_api_base_url_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_BASE_URL", "https://crisis-resource-api.onrender.com/")
    app = _import_dashboard()
    # Trailing slash should be stripped by get_api_base().
    assert app.get_api_base() == "https://crisis-resource-api.onrender.com"


def test_mode_messages_are_nonempty_strings() -> None:
    app = _import_dashboard()
    message_attrs = [
        "BACKEND_UNAVAILABLE_MESSAGE",
        "OPTIMIZED_TRANSFER_UNAVAILABLE_MESSAGE",
        "AI_BRIEF_UNAVAILABLE_MESSAGE",
        "RAG_KEYWORD_FALLBACK_NOTE",
        "OPTIMIZED_TRANSFER_NOTE",
    ]
    for attr in message_attrs:
        value = getattr(app, attr, None)
        assert isinstance(value, str), f"{attr} should be a string"
        assert value.strip(), f"{attr} should not be empty"
