from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


def load_harness_meta(path: str) -> dict[str, Any] | None:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _extract_revision(harness_version: str | None) -> int:
    if not harness_version:
        return 0
    value = harness_version.strip().lower()
    if value.startswith("v") and value[1:].isdigit():
        return int(value[1:])
    return 0


def build_next_harness_meta(
    *,
    current_meta: dict[str, Any] | None,
    source_run_id: str,
) -> dict[str, Any]:
    current_version = None if current_meta is None else str(current_meta.get("harness_version", ""))
    next_revision = _extract_revision(current_version) + 1
    return {
        "harness_version": f"v{next_revision}",
        "revision": next_revision,
        "previous_harness_version": current_version or None,
        "source_run_id": source_run_id,
        "promoted_at": datetime.now(timezone.utc).isoformat(),
    }
