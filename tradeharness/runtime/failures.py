from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from tradeharness.evolution.schemas import build_episode_record, build_step_record
from tradeharness.evolution.storage.trajectories import append_episode_record


def format_exception(exc: BaseException) -> str:
    return f"{exc.__class__.__name__}: {exc}"


def append_runtime_incident(
    path: str,
    *,
    component: str,
    phase: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    payload = {
        "incident_id": f"incident-{uuid4().hex}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "component": component,
        "phase": phase,
        "message": message,
        "details": details or {},
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def append_failure_episode(
    *,
    trajectory_log_path: str,
    task_id: str,
    harness_version: str,
    symbol: str,
    mode: str,
    phase: str,
    error_message: str,
    termination_reason: str,
    final_tag: str = "runtime_failure",
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    step = build_step_record(
        step_index=1,
        observation={"phase": phase},
        decision_summary=error_message,
        action={"final_response": final_tag},
        harness_intervention={"decision": "ERROR", "layer": "runtime"},
        environment_feedback={"error": error_message},
    )
    episode = build_episode_record(
        episode_id=f"episode-{uuid4().hex}",
        task_id=task_id,
        harness_version=harness_version,
        symbol=symbol,
        mode=mode,
        started_at=now,
        ended_at=now,
        final_status="FAILED",
        termination_reason=termination_reason,
        steps=[step],
        final_outcome={"final": final_tag, "reason": error_message},
    )
    append_episode_record(trajectory_log_path, episode)
