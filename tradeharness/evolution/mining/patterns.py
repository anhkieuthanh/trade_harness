from __future__ import annotations

from typing import Any

from tradeharness.evolution.classification.mapper import map_failure_to_layer


def mine_failure_patterns(annotations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in annotations:
        evidence = item.get("evidence", [])
        signature = str(evidence[0]) if evidence else item["primary_failure_type"]
        key = (item["primary_failure_type"], signature)
        grouped.setdefault(key, []).append(item)

    patterns: list[dict[str, Any]] = []
    for (failure_type, signature), items in grouped.items():
        patterns.append(
            {
                "pattern_id": f"{failure_type}:{abs(hash(signature))}",
                "pattern_type": failure_type,
                "frequency": len(items),
                "target_layer": map_failure_to_layer(failure_type),
                "supporting_episodes": [item["episode_id"] for item in items],
                "representative_evidence": items[0].get("evidence", []),
            }
        )
    return sorted(patterns, key=lambda item: item["frequency"], reverse=True)
