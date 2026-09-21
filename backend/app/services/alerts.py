"""
app/services/alerts.py
======================
HeatSense -- EXTREME HTSI Alert Notification Service.

PURPOSE
-------
Detects when any ward/area assessment crosses into the EXTREME tier (HTSI >= 76)
and dispatches webhook notifications to a configured municipal disaster management
endpoint.

DESIGN RULES
------------
- Pure notification side-effect. Does NOT modify or override any assessment.
- Webhook calls are fire-and-forget async BackgroundTask -- never block the API.
- If the webhook call fails, error is logged and swallowed.
- If HEATSENSE_ALERT_WEBHOOK_URL is not set, alerts are silently disabled.

ENVIRONMENT VARIABLES
---------------------
  HEATSENSE_ALERT_WEBHOOK_URL   Webhook target URL (required to enable alerts).
  HEATSENSE_ALERT_TIMEOUT_S     HTTP timeout in seconds for webhook call (default: 5).
  HEATSENSE_ALERT_SECRET        Optional Bearer token sent in Authorization header.

WEBHOOK PAYLOAD (JSON POST body)
---------------------------------
  {
    "event":       "EXTREME_HTSI_ALERT",
    "system":      "HeatSense-SIH26083",
    "timestamp":   "2026-09-19T14:00:00+05:30",
    "area_id":     "H07",
    "area_name":   "Haldia Port Zone East",
    "ward_number": 14,
    "htsi":        82,
    "risk_level":  "EXTREME",
    "heat_index_c": 51.3,
    "recommended_actions": { ... }
  }
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger("heatsense.alerts")

_IST = timezone(timedelta(hours=5, minutes=30))
_EXTREME_TIER = "EXTREME"
_ALERT_EVENT_NAME = "EXTREME_HTSI_ALERT"
_SYSTEM_ID = "HeatSense-SIH26083"


def _get_config():
    url = os.environ.get("HEATSENSE_ALERT_WEBHOOK_URL", "").strip()
    if not url:
        return None
    timeout_s = float(os.environ.get("HEATSENSE_ALERT_TIMEOUT_S", "5"))
    secret = os.environ.get("HEATSENSE_ALERT_SECRET", "").strip()
    return {"url": url, "timeout_s": timeout_s, "secret": secret}


def _build_payload(area_id, area_name, ward_number, assessment):
    now_ist = datetime.now(_IST).isoformat()
    return {
        "event": _ALERT_EVENT_NAME,
        "system": _SYSTEM_ID,
        "timestamp": now_ist,
        "area_id": area_id,
        "area_name": area_name,
        "ward_number": ward_number,
        "htsi": assessment.get("htsi"),
        "risk_level": assessment.get("risk_level"),
        "heat_index_c": (
            assessment.get("supporting_metrics", {}).get("heat_index_c")
            if assessment.get("supporting_metrics")
            else None
        ),
        "recommended_actions": assessment.get("recommended_actions"),
    }


async def dispatch_extreme_alert(area_id, area_name, ward_number, assessment):
    """
    Async fire-and-forget: post EXTREME_HTSI_ALERT webhook if configured.

    Designed to run as a FastAPI BackgroundTask. Never raises.
    """
    config = _get_config()
    if config is None:
        return

    if assessment.get("risk_level") != _EXTREME_TIER:
        return

    payload = _build_payload(area_id, area_name, ward_number, assessment)

    headers = {"Content-Type": "application/json"}
    if config["secret"]:
        headers["Authorization"] = f"Bearer {config['secret']}"

    try:
        import httpx

        async with httpx.AsyncClient(timeout=config["timeout_s"]) as client:
            resp = await client.post(config["url"], json=payload, headers=headers)
            if resp.is_success:
                logger.info(
                    "EXTREME alert dispatched for %s (HTSI=%s) -> HTTP %d",
                    area_id, payload["htsi"], resp.status_code,
                )
            else:
                logger.warning(
                    "EXTREME alert webhook non-2xx for %s: HTTP %d %s",
                    area_id, resp.status_code, resp.text[:200],
                )
    except Exception as exc:
        logger.error(
            "EXTREME alert dispatch failed for %s: %s: %s",
            area_id, type(exc).__name__, exc,
        )
