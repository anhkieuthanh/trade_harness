from __future__ import annotations

import json
import os


def load_active_skill_cards(path: str | None = None) -> list[dict[str, object]]:
    resolved_path = path or os.getenv(
        "ACTIVE_SKILLS_ARTIFACT_PATH",
        "tradeharness/evolution/artifacts/current/skills.json",
    )
    if not os.path.exists(resolved_path):
        return []
    with open(resolved_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [dict(item) for item in payload.get("skills", [])]


def get_skill_library() -> list[dict[str, object]]:
    base_skills = [
        {
            "skill_id": "entry_confirm_state_first",
            "title": "Entry confirmation after state inspection",
            "tags": ["entry", "inspection", "btcusdt", "binance-futures"],
            "when_to_use": "Before calling open_long or open_short on BTCUSDT.",
            "procedure": (
                "Inspect market snapshot first, then inspect position state, then inspect balance. "
                "Only consider an entry after all three are consistent with the idea."
            ),
            "anti_patterns": (
                "Do not jump from user intent directly to open_long or open_short without "
                "market, position, and balance checks."
            ),
        },
        {
            "skill_id": "entry_thesis_short_summary",
            "title": "Short entry thesis before execution",
            "tags": ["entry", "thesis", "execution", "btcusdt"],
            "when_to_use": "Right before choosing open_long or open_short.",
            "procedure": (
                "Summarize what was inspected, what direction the recent state suggests, "
                "and why the execution tool matches that state."
            ),
            "anti_patterns": (
                "Do not use an execution tool when the inspected state is incomplete, "
                "contradictory, or not yet summarized."
            ),
        },
        {
            "skill_id": "entry_avoid_rushed_execution",
            "title": "Avoid rushed execution after observation",
            "tags": ["entry", "discipline", "execution-sequence"],
            "when_to_use": "When recent candles look active and the model wants to act quickly.",
            "procedure": (
                "Treat observation and execution as separate steps. After inspection, pause to "
                "form the execution intent before requesting an order tool."
            ),
            "anti_patterns": (
                "Do not treat get_market_snapshot alone as enough context for immediate execution."
            ),
        },
    ]
    return base_skills + load_active_skill_cards()
