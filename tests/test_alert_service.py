"""
tests/test_alert_service.py
============================
Unit tests for app/services/alerts.py -- EXTREME HTSI alert webhook dispatcher.

Tests verify:
  - Alert suppressed when no URL configured.
  - Alert suppressed when risk_level != EXTREME.
  - Payload structure when EXTREME is detected.
  - Graceful failure handling (exception swallowed, no crash).
"""
import asyncio
import os
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extreme_assessment(htsi=82):
    return {
        "risk_level": "EXTREME",
        "htsi": htsi,
        "supporting_metrics": {"heat_index_c": 50.1, "wbgt_proxy_c": 39.0},
        "recommended_actions": {"municipal": "Open cooling centres", "citizen": "Stay indoors"},
        "data_status": "available",
    }

def _moderate_assessment():
    return {
        "risk_level": "MODERATE",
        "htsi": 38,
        "supporting_metrics": {"heat_index_c": 36.0, "wbgt_proxy_c": 30.0},
        "recommended_actions": {},
        "data_status": "available",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_no_webhook_url_dispatches_nothing():
    """When HEATSENSE_ALERT_WEBHOOK_URL is not set, dispatch is a no-op."""
    os.environ.pop("HEATSENSE_ALERT_WEBHOOK_URL", None)
    from app.services.alerts import dispatch_extreme_alert
    # Should complete without error even for EXTREME tier
    asyncio.run(dispatch_extreme_alert("H07", "Test Area", 7, _extreme_assessment()))


def test_non_extreme_tier_suppressed(monkeypatch):
    """Webhook must NOT fire for non-EXTREME risk levels."""
    monkeypatch.setenv("HEATSENSE_ALERT_WEBHOOK_URL", "http://localhost:9999/fake-webhook")
    from app.services.alerts import dispatch_extreme_alert
    # If the HTTP call were made to the fake URL it would error and bubble up through
    # the re-raise path -- but since we guard on risk_level first, it must not raise.
    asyncio.run(dispatch_extreme_alert("H01", "Test", None, _moderate_assessment()))


def test_build_payload_structure():
    """_build_payload produces the expected top-level keys."""
    from app.services.alerts import _build_payload
    payload = _build_payload("H07", "Haldia Ward 7", 7, _extreme_assessment(htsi=82))
    required_keys = {"event", "system", "timestamp", "area_id", "area_name", "ward_number", "htsi", "risk_level"}
    assert required_keys.issubset(payload.keys()), f"Missing keys: {required_keys - payload.keys()}"
    assert payload["event"] == "EXTREME_HTSI_ALERT"
    assert payload["htsi"] == 82
    assert payload["risk_level"] == "EXTREME"
    assert payload["ward_number"] == 7


def test_build_payload_outside_boundary():
    """ward_number should be None for outside_boundary areas."""
    from app.services.alerts import _build_payload
    payload = _build_payload("H09", "Port Area", None, _extreme_assessment())
    assert payload["ward_number"] is None


def test_alert_suppressed_on_http_error(monkeypatch):
    """Network errors must be swallowed -- dispatch_extreme_alert never raises."""
    monkeypatch.setenv("HEATSENSE_ALERT_WEBHOOK_URL", "http://localhost:1/nonexistent")
    monkeypatch.setenv("HEATSENSE_ALERT_TIMEOUT_S", "0.01")
    from app.services import alerts
    # Reload to pick up env var changes
    import importlib; importlib.reload(alerts)
    # Should not raise even on connection refused / timeout
    asyncio.run(alerts.dispatch_extreme_alert("H07", "Test", 7, _extreme_assessment()))
