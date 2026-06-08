from __future__ import annotations

from typing import Any


def build_step_record(
    *,
    step_index: int,
    observation: dict[str, Any],
    decision_summary: str,
    action: dict[str, Any],
    harness_intervention: dict[str, Any],
    environment_feedback: dict[str, Any],
) -> dict[str, Any]:
    return {
        "step_index": step_index,
        "observation": observation,
        "decision_summary": decision_summary,
        "action": action,
        "harness_intervention": harness_intervention,
        "environment_feedback": environment_feedback,
    }


def build_episode_record(
    *,
    episode_id: str,
    task_id: str,
    harness_version: str,
    symbol: str,
    mode: str,
    started_at: str,
    ended_at: str,
    final_status: str,
    termination_reason: str,
    steps: list[dict[str, Any]],
    final_outcome: dict[str, Any],
) -> dict[str, Any]:
    return {
        "episode_id": episode_id,
        "task_id": task_id,
        "harness_version": harness_version,
        "symbol": symbol,
        "mode": mode,
        "started_at": started_at,
        "ended_at": ended_at,
        "final_status": final_status,
        "termination_reason": termination_reason,
        "steps": steps,
        "final_outcome": final_outcome,
    }


def build_annotation_record(**payload: Any) -> dict[str, Any]:
    return dict(payload)


def build_update_candidate(**payload: Any) -> dict[str, Any]:
    return dict(payload)
