from __future__ import annotations

from typing import Any


def should_promote_candidate(
    *,
    candidate: dict[str, Any],
    regression_note: dict[str, Any],
    minimum_support: int,
) -> dict[str, Any]:
    support_count = len(candidate.get("supporting_episodes", []))
    flags = set(regression_note.get("flags", []))
    hard_flags = {
        "high_overtrigger_risk",
        "ambiguous_action_override",
        "conflicts_with_existing_rule",
    }
    if support_count < minimum_support:
        return {"promote": False, "reason": "insufficient_support"}
    if flags & hard_flags:
        return {"promote": False, "reason": "hard_regression_flag"}
    return {
        "promote": candidate["target_layer"] in {"layer_1", "layer_2"},
        "reason": "layer_policy",
    }


def build_promotion_report(
    *,
    candidates: list[dict[str, Any]],
    regression_notes: list[dict[str, Any]],
    minimum_support: int,
) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    for candidate, note in zip(candidates, regression_notes):
        decision = should_promote_candidate(
            candidate=candidate,
            regression_note=note,
            minimum_support=minimum_support,
        )
        report.append(
            {
                "target_layer": candidate["target_layer"],
                "problem_pattern": candidate["problem_pattern"],
                "decision": decision,
            }
        )
    return report
