from __future__ import annotations

from collections import defaultdict
from typing import Any


def is_episode_pass(episode: dict[str, Any]) -> bool:
    if episode.get("final_status") != "SUCCESS":
        return False
    termination_reason = str(episode.get("termination_reason") or "").strip().lower()
    non_pass_terminations = {
        "risk_guard_hold",
        "manual_only_hold",
        "random_flip_hold",
    }
    return termination_reason not in non_pass_terminations


def compute_pass_at_1(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(episodes)
    passed = sum(1 for episode in episodes if is_episode_pass(episode))
    return {
        "total_episodes": total,
        "passed_episodes": passed,
        "pass_at_1": (passed / total) if total else 0.0,
    }


def summarize_pass_metrics(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "pass_at_1": compute_pass_at_1(episodes),
    }


def summarize_pass_metrics_by_harness_version(
    episodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for episode in episodes:
        grouped[episode.get("harness_version", "unknown")].append(episode)

    summaries: list[dict[str, Any]] = []
    for harness_version, version_episodes in sorted(grouped.items()):
        metrics = summarize_pass_metrics(version_episodes)
        summaries.append(
            {
                "harness_version": harness_version,
                "episode_count": len(version_episodes),
                "pass_at_1": metrics["pass_at_1"]["pass_at_1"],
            }
        )

    return summaries
