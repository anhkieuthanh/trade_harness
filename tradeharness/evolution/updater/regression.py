from __future__ import annotations

from typing import Any


def build_regression_note(*, candidate: dict[str, Any]) -> dict[str, Any]:
    target_layer = candidate["target_layer"]
    if target_layer in {"layer_1", "layer_3", "layer_4"}:
        return {
            "target_layer": target_layer,
            "risk_summary": "Check for over-trigger behavior that may block valid actions.",
            "flags": [],
            "checks": [
                "Would this change reject a previously valid execution?",
                "Would this change trigger on normal inspection-only behavior?",
            ],
        }
    return {
        "target_layer": target_layer,
        "risk_summary": "Check whether the new guidance dilutes retrieval quality.",
        "flags": [],
        "checks": [
            "Would this skill crowd out more relevant skills?",
            "Would this advice conflict with existing procedures?",
        ],
    }
