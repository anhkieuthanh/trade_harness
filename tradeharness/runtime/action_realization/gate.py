from __future__ import annotations

import json
import os
from typing import Any


EXECUTION_TOOL_NAMES = {"open_long", "open_short", "close_position"}
MAX_ACTION_REALIZATION_RETRIES = 2


def load_active_action_rules(path: str | None = None) -> list[dict[str, Any]]:
    resolved_path = path or os.getenv(
        "ACTIVE_ACTION_RULES_ARTIFACT_PATH",
        "tradeharness/evolution/artifacts/current/action_rules.json",
    )
    if not os.path.exists(resolved_path):
        return []
    with open(resolved_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [dict(item) for item in payload.get("rules", [])]


def _matches_dynamic_action_rule(
    *,
    rule: dict[str, Any],
    tool_name: str,
    position_state: dict[str, Any],
    arguments: dict[str, Any],
) -> bool:
    rule_tool_name = str(rule.get("tool_name", ""))
    if rule_tool_name not in {tool_name, "*"}:
        return False

    condition = rule.get("condition", {})
    if not isinstance(condition, dict):
        return False

    kind = str(condition.get("kind", ""))
    if kind == "position_side_is":
        return str(position_state.get("side", "")).upper() == str(
            condition.get("value", "")
        ).upper()
    if kind == "is_open":
        return bool(position_state.get("is_open", False)) == bool(
            condition.get("value", False)
        )
    if kind == "argument_equals":
        field = str(condition.get("field", ""))
        return arguments.get(field) == condition.get("value")
    return False


def realize_action(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    position_state: dict[str, Any],
    inspected_state: dict[str, bool],
) -> dict[str, Any]:
    if tool_name not in EXECUTION_TOOL_NAMES:
        return {
            "decision": "EXECUTE",
            "reason": "Observation tool does not require action realization blocking.",
            "details": {"tool_name": tool_name, "arguments": arguments},
        }

    missing_checks = [
        label
        for label, was_seen in inspected_state.items()
        if label in {"market_snapshot", "position", "balance"} and not was_seen
    ]
    if missing_checks:
        return {
            "decision": "BLOCK",
            "reason": (
                "Execution blocked because required state was not inspected: "
                + ", ".join(missing_checks)
            ),
            "details": {
                "tool_name": tool_name,
                "missing_checks": missing_checks,
                "arguments": arguments,
            },
        }

    side = str(position_state.get("side", "FLAT")).upper()
    is_open = bool(position_state.get("is_open", False))

    if tool_name == "close_position" and not is_open:
        return {
            "decision": "BLOCK",
            "reason": "No open position is available to close.",
            "details": {"tool_name": tool_name, "position_state": position_state},
        }

    if tool_name in {"open_long", "open_short"} and is_open:
        return {
            "decision": "BLOCK",
            "reason": f"An open position is already open ({side}); do not open another entry action now.",
            "details": {"tool_name": tool_name, "position_state": position_state},
        }

    for rule in load_active_action_rules():
        if _matches_dynamic_action_rule(
            rule=rule,
            tool_name=tool_name,
            position_state=position_state,
            arguments=arguments,
        ):
            return {
                "decision": str(rule.get("decision", "BLOCK")).upper(),
                "reason": str(rule.get("message", "Dynamic action rule triggered.")),
                "details": {
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "rule_id": rule.get("rule_id"),
                },
            }

    return {
        "decision": "EXECUTE",
        "reason": "Action passed state-validity checks.",
        "details": {"tool_name": tool_name, "arguments": arguments},
    }
