from __future__ import annotations

import json
import os

BASE_EXECUTION_SAFETY_RULES = [
    "Inspect market state before trading.",
    "Inspect current position before opening or closing.",
    "Inspect available balance before opening exposure.",
    "Prefer observation tools before execution tools.",
    "Do not act with incomplete state.",
]


TOOL_CONTRACT_RULES = {
    "get_market_snapshot": [
        "Use this first to inspect recent price and candles.",
        "This is a state-inspection tool, not an execution tool.",
    ],
    "get_balance": [
        "Use this before opening exposure to confirm capital context.",
        "Do not assume sizing safety without checking balance.",
    ],
    "get_position": [
        "Use this before open_long, open_short, or close_position.",
        "Do not assume the account is flat without checking position.",
    ],
    "open_long": [
        "Only use after inspecting market state, get_position, and get_balance.",
        "Do not use as a discovery step.",
    ],
    "open_short": [
        "Only use after inspecting market state, get_position, and get_balance.",
        "Do not use as a discovery step.",
    ],
    "close_position": [
        "Only use after checking get_position.",
        "Do not call this unless an open position exists.",
    ],
}


def load_active_contract_clauses(path: str | None = None) -> list[str]:
    resolved_path = path or os.getenv(
        "ACTIVE_CONTRACT_ARTIFACT_PATH",
        "tradeharness/evolution/artifacts/current/contract.json",
    )
    if not os.path.exists(resolved_path):
        return []
    with open(resolved_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [
        str(item["rule_text"])
        for item in payload.get("clauses", [])
        if item.get("rule_text")
    ]


def build_environment_contract(symbol: str) -> str:
    rules = BASE_EXECUTION_SAFETY_RULES + load_active_contract_clauses()
    rendered_rules = "\n".join(f"- {rule}" for rule in rules)
    return "\n".join(
        [
            f"Environment Contract for {symbol} on Binance Futures Testnet:",
            rendered_rules,
            "Use get_market_snapshot, get_position, and get_balance before requesting execution tools.",
            "Before requesting any execution tool, summarize what state was inspected and why the action follows.",
        ]
    )


def augment_tool_description(tool_name: str, base_description: str) -> str:
    rules = TOOL_CONTRACT_RULES.get(tool_name, [])
    if not rules:
        return base_description
    return f"{base_description} Contract: {' '.join(rules)}"
