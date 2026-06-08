from __future__ import annotations

from collections import Counter
from typing import Any


def regulate_trajectory(
    *,
    history: list[dict[str, Any]],
    steps_remaining: int,
    final_answer_present: bool,
) -> dict[str, Any]:
    if final_answer_present:
        return {
            "decision": "ALLOW",
            "reason": "Final answer already present.",
            "details": {},
        }

    recent_tools = [item["tool_name"] for item in history if item.get("event") == "tool"]
    if len(recent_tools) >= 3 and len(set(recent_tools[-3:])) == 1:
        return {
            "decision": "WARN",
            "reason": f"Agent is repeating the same tool too often: {recent_tools[-1]}",
            "details": {"tool_name": recent_tools[-1]},
        }

    block_reasons = [
        item["block_reason"]
        for item in history
        if item.get("event") == "block" and item.get("block_reason")
    ]
    repeated_blocks = Counter(block_reasons)
    for reason, count in repeated_blocks.items():
        if count >= 3:
            return {
                "decision": "STOP",
                "reason": f"Repeated blocked action detected: {reason}",
                "details": {"block_reason": reason, "count": count},
            }

    observation_only_events = [
        item
        for item in history[-5:]
        if item.get("event") == "tool"
        and item.get("tool_name") in {"get_market_snapshot", "get_position", "get_balance"}
    ]
    if len(observation_only_events) >= 5:
        return {
            "decision": "WARN",
            "reason": "Trajectory appears stagnant: repeated observation without clear progress.",
            "details": {"window_size": len(observation_only_events)},
        }

    if steps_remaining <= 1:
        return {
            "decision": "WARN",
            "reason": "Budget is nearly exhausted; conclude now or return a no-trade summary.",
            "details": {"steps_remaining": steps_remaining},
        }

    return {
        "decision": "ALLOW",
        "reason": "Trajectory is currently healthy.",
        "details": {},
    }
