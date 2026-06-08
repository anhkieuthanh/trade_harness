from __future__ import annotations

from collections import Counter
from typing import Any

from tradeharness.evolution.classification.mapper import map_failure_to_layer
from tradeharness.evolution.schemas import build_update_candidate


def _suggest_change_for_failure(failure_type: str) -> str:
    suggestions = {
        "action_realization": "Add or tighten action validators and canonicalizers in Layer 3.",
        "environment_contract": "Add stricter contract clauses and tool guidance in Layer 1.",
        "trajectory_degeneration": "Add monitors or counters to Layer 4 to catch the repeated pattern earlier.",
        "residual_reasoning": "Add a new distilled procedural skill to Layer 2.",
    }
    return suggestions[failure_type]


def build_update_candidates(
    *,
    annotations: list[dict[str, Any]],
    current_harness: dict[str, Any],
    design_guide: dict[str, Any],
) -> list[dict[str, Any]]:
    del current_harness, design_guide

    use_patterns = bool(annotations) and "pattern_type" in annotations[0]
    top_failures = []
    if use_patterns:
        top_failures = [
            (item["pattern_type"], item["frequency"], item)
            for item in annotations[:2]
        ]
    else:
        counts = Counter(item["primary_failure_type"] for item in annotations)
        top_failures = [(failure_type, count, None) for failure_type, count in counts.most_common(2)]
    candidates: list[dict[str, Any]] = []

    for failure_type, _count, pattern in top_failures:
        supporting_episodes = (
            pattern["supporting_episodes"]
            if pattern is not None
            else [
                item["episode_id"]
                for item in annotations
                if item["primary_failure_type"] == failure_type
            ]
        )
        candidates.append(
            build_update_candidate(
                target_layer=map_failure_to_layer(failure_type),
                problem_pattern=failure_type,
                suggested_change=_suggest_change_for_failure(failure_type),
                confidence="medium",
                supporting_episodes=supporting_episodes,
            )
        )

    return candidates
