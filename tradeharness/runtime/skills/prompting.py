from __future__ import annotations

import json
from typing import Any


def build_skill_query(
    *,
    user_task: str,
    symbol: str,
    interval: str,
    market_snapshot: dict[str, Any] | None,
    position_state: dict[str, Any] | None,
    tool_intent: str,
) -> str:
    snapshot_text = json.dumps(market_snapshot or {}, sort_keys=True)
    position_text = json.dumps(position_state or {}, sort_keys=True)
    return "\n".join(
        [
            f"User task: {user_task}",
            f"Symbol: {symbol}",
            f"Interval: {interval}",
            f"Market snapshot: {snapshot_text}",
            f"Position state: {position_text}",
            f"Tool intent: {tool_intent}",
        ]
    )


def render_relevant_skills_block(skills: list[dict[str, object]]) -> str:
    if not skills:
        return "Relevant Skills:\n- None selected."
    lines = ["Relevant Skills:"]
    for skill in skills:
        lines.extend(
            [
                f"- {skill['title']}",
                f"  When to use: {skill['when_to_use']}",
                f"  Procedure: {skill['procedure']}",
                f"  Anti-patterns: {skill['anti_patterns']}",
            ]
        )
    return "\n".join(lines)
