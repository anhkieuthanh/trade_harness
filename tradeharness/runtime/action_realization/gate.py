from __future__ import annotations

from typing import Any


EXECUTION_TOOL_NAMES = {"open_long", "open_short", "close_position"}
MAX_ACTION_REALIZATION_RETRIES = 2


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

    return {
        "decision": "EXECUTE",
        "reason": "Action passed state-validity checks.",
        "details": {"tool_name": tool_name, "arguments": arguments},
    }
