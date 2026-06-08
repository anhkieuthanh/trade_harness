from __future__ import annotations

from collections import Counter
import json
import os
from typing import Any


def load_active_trajectory_rules(path: str | None = None) -> list[dict[str, Any]]:
    resolved_path = path or os.getenv(
        "ACTIVE_TRAJECTORY_RULES_ARTIFACT_PATH",
        "tradeharness/evolution/artifacts/current/trajectory_rules.json",
    )
    if not os.path.exists(resolved_path):
        return []
    with open(resolved_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [dict(item) for item in payload.get("rules", [])]


def _evaluate_dynamic_trajectory_rules(
    *,
    history: list[dict[str, Any]],
    steps_remaining: int,
) -> dict[str, Any] | None:
    for rule in load_active_trajectory_rules():
        pattern_type = str(rule.get("pattern_type", ""))
        threshold = int(rule.get("threshold", 0) or 0)
        decision = str(rule.get("decision", "WARN")).upper()
        message = str(rule.get("message", "Dynamic trajectory rule triggered."))

        if pattern_type == "repeat_tool":
            window = int(rule.get("window", 3) or 3)
            watched_tools = set(rule.get("watched_tools", []))
            recent_tools = [
                item["tool_name"] for item in history[-window:] if item.get("event") == "tool"
            ]
            if len(recent_tools) >= threshold and len(set(recent_tools)) == 1:
                if not watched_tools or recent_tools[-1] in watched_tools:
                    return {"decision": decision, "reason": message, "details": {"rule_id": rule.get("rule_id")}}

        if pattern_type == "repeat_block_reason":
            block_reason = str(rule.get("block_reason", ""))
            count = sum(
                1
                for item in history
                if item.get("event") == "block"
                and str(item.get("block_reason", "")) == block_reason
            )
            if count >= threshold:
                return {"decision": decision, "reason": message, "details": {"rule_id": rule.get("rule_id")}}

        if pattern_type == "observation_stagnation":
            window = int(rule.get("window", 5) or 5)
            watched_tools = set(
                rule.get(
                    "watched_tools",
                    ["get_market_snapshot", "get_position", "get_balance"],
                )
            )
            count = sum(
                1
                for item in history[-window:]
                if item.get("event") == "tool" and item.get("tool_name") in watched_tools
            )
            if count >= threshold:
                return {"decision": decision, "reason": message, "details": {"rule_id": rule.get("rule_id")}}

        if pattern_type == "low_budget" and steps_remaining <= threshold:
            return {"decision": decision, "reason": message, "details": {"rule_id": rule.get("rule_id")}}

    return None


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

    dynamic_result = _evaluate_dynamic_trajectory_rules(
        history=history,
        steps_remaining=steps_remaining,
    )
    if dynamic_result is not None:
        return dynamic_result

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
