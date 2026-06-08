from __future__ import annotations

import json
import os
import tempfile
import unittest

from tradeharness.tools.binance import BinanceToolset
from tradeharness.integrations.lmstudio.client import extract_tool_requests
from tradeharness.runtime.contracts.environment import (
    augment_tool_description,
    build_environment_contract,
)
from tradeharness.runtime.action_realization.gate import realize_action
from tradeharness.runtime.agent import (
    build_action_block_feedback,
    build_system_prompt,
    build_trajectory_stop_summary,
    build_trajectory_warning_feedback,
)
from tradeharness.runtime.skills.library import get_skill_library
from tradeharness.runtime.skills.prompting import (
    build_skill_query,
    render_relevant_skills_block,
)
from tradeharness.runtime.skills.retrieval import retrieve_relevant_skills
from tradeharness.runtime.trajectory_regulation.monitor import regulate_trajectory


class FakeBinanceClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def get_price(self, symbol: str) -> float:
        self.calls.append(("get_price", (symbol,)))
        return 63000.0

    def get_klines(self, symbol: str, interval: str, limit: int):
        self.calls.append(("get_klines", (symbol, interval, limit)))
        return []

    def get_available_balance(self, asset: str = "USDT") -> float:
        self.calls.append(("get_available_balance", (asset,)))
        return 1000.0

    def get_position(self, symbol: str):
        self.calls.append(("get_position", (symbol,)))

        class Position:
            side = "FLAT"
            quantity = 0.0
            entry_price = 0.0

        return Position()

    def get_symbol_filters(self, symbol: str):
        self.calls.append(("get_symbol_filters", (symbol,)))

        class Filters:
            step_size = 0.001
            min_qty = 0.001

        return Filters()

    def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        reduce_only: bool = False,
    ):
        self.calls.append(("place_market_order", (symbol, side, quantity, reduce_only)))
        return {"symbol": symbol, "side": side, "quantity": quantity, "reduceOnly": reduce_only}


class ExtractToolRequestsTests(unittest.TestCase):
    def test_extracts_native_tool_calls(self) -> None:
        response = {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "get_market_snapshot",
                                    "arguments": '{"symbol":"BTCUSDT","interval":"1m","limit":5}',
                                },
                            }
                        ],
                    }
                }
            ]
        }

        tool_requests = extract_tool_requests(response)

        self.assertEqual(len(tool_requests), 1)
        self.assertEqual(tool_requests[0].name, "get_market_snapshot")
        self.assertEqual(tool_requests[0].arguments["symbol"], "BTCUSDT")

    def test_extracts_fenced_json_tool_request(self) -> None:
        response = {
            "choices": [
                {
                    "message": {
                        "content": '```json\n{"tool":"get_balance","arguments":{"asset":"USDT"}}\n```',
                        "tool_calls": [],
                    }
                }
            ]
        }

        tool_requests = extract_tool_requests(response)

        self.assertEqual(len(tool_requests), 1)
        self.assertEqual(tool_requests[0].name, "get_balance")
        self.assertEqual(tool_requests[0].arguments["asset"], "USDT")

    def test_returns_empty_for_non_json_plain_text(self) -> None:
        response = {
            "choices": [
                {
                    "message": {
                        "content": "I inspected the state and no execution is recommended.",
                        "tool_calls": [],
                    }
                }
            ]
        }

        tool_requests = extract_tool_requests(response)

        self.assertEqual(tool_requests, [])


class BinanceToolsetTests(unittest.TestCase):
    def test_get_market_snapshot_combines_price_and_candles(self) -> None:
        toolset = BinanceToolset(FakeBinanceClient(), trade_size_percent=10.0)

        result = toolset.run_tool(
            "get_market_snapshot",
            {"symbol": "BTCUSDT", "interval": "1m", "limit": 5},
        )

        self.assertEqual(result["symbol"], "BTCUSDT")
        self.assertEqual(result["price"], 63000.0)
        self.assertIn("candles", result)

    def test_open_long_uses_percent_balance_sizing(self) -> None:
        toolset = BinanceToolset(FakeBinanceClient(), trade_size_percent=10.0)

        result = toolset.run_tool("open_long", {"symbol": "BTCUSDT"})

        self.assertEqual(result["side"], "BUY")
        self.assertAlmostEqual(result["quantity"], 0.001, places=6)

    def test_get_balance_normalizes_symbol_like_asset_to_usdt(self) -> None:
        toolset = BinanceToolset(FakeBinanceClient(), trade_size_percent=10.0)

        result = toolset.run_tool("get_balance", {"asset": "BTCUSDT"})

        self.assertEqual(result["asset"], "USDT")
        self.assertEqual(result["available_balance"], 1000.0)

    def test_tool_definitions_include_contract_augmentation(self) -> None:
        toolset = BinanceToolset(FakeBinanceClient(), trade_size_percent=10.0)

        definitions = toolset.definitions()
        open_long = next(
            item for item in definitions if item["function"]["name"] == "open_long"
        )

        self.assertIn("Contract:", open_long["function"]["description"])
        self.assertIn("Only use after", open_long["function"]["description"])


class EnvironmentContractTests(unittest.TestCase):
    def test_build_environment_contract_mentions_execution_safety_rules(self) -> None:
        contract = build_environment_contract(symbol="BTCUSDT")

        self.assertIn("inspect market state before trading", contract.lower())
        self.assertIn("get_position", contract)
        self.assertIn("Binance Futures Testnet", contract)

    def test_augment_tool_description_adds_tool_specific_contract(self) -> None:
        description = augment_tool_description(
            tool_name="open_long",
            base_description="Open a long futures position.",
        )

        self.assertIn("Open a long futures position.", description)
        self.assertIn("Only use after", description)
        self.assertIn("get_position", description)


class RuntimePromptTests(unittest.TestCase):
    def test_build_system_prompt_includes_environment_contract(self) -> None:
        prompt = build_system_prompt(
            symbol="BTCUSDT",
            relevant_skills_block="Relevant Skills:\n- Sample skill",
        )

        self.assertIn("You are a BTCUSDT Binance Futures Testnet trading agent.", prompt)
        self.assertIn("Environment Contract for BTCUSDT on Binance Futures Testnet:", prompt)
        self.assertIn("Inspect market state before trading.", prompt)
        self.assertIn("Relevant Skills:", prompt)


class ActionRealizationRuntimeTests(unittest.TestCase):
    def test_build_action_block_feedback_contains_block_reason(self) -> None:
        feedback = build_action_block_feedback(
            {
                "decision": "BLOCK",
                "reason": "No open position is available to close.",
                "details": {"tool_name": "close_position"},
            }
        )

        self.assertIn("Action blocked", feedback)
        self.assertIn("No open position is available to close.", feedback)
        self.assertIn("corrected action", feedback.lower())


class TrajectoryRegulationTests(unittest.TestCase):
    def test_warns_on_repeated_same_tool_pattern(self) -> None:
        result = regulate_trajectory(
            history=[
                {"event": "tool", "tool_name": "get_balance", "blocked": False},
                {"event": "tool", "tool_name": "get_balance", "blocked": False},
                {"event": "tool", "tool_name": "get_balance", "blocked": False},
            ],
            steps_remaining=4,
            final_answer_present=False,
        )

        self.assertEqual(result["decision"], "WARN")
        self.assertIn("repeating", result["reason"].lower())

    def test_stops_on_repeated_same_block_reason(self) -> None:
        result = regulate_trajectory(
            history=[
                {
                    "event": "block",
                    "tool_name": "open_long",
                    "block_reason": "No open position is available to close.",
                },
                {
                    "event": "block",
                    "tool_name": "open_long",
                    "block_reason": "No open position is available to close.",
                },
                {
                    "event": "block",
                    "tool_name": "open_long",
                    "block_reason": "No open position is available to close.",
                },
            ],
            steps_remaining=4,
            final_answer_present=False,
        )

        self.assertEqual(result["decision"], "STOP")
        self.assertIn("block", result["reason"].lower())

    def test_warns_when_budget_is_low_without_final_answer(self) -> None:
        result = regulate_trajectory(
            history=[{"event": "tool", "tool_name": "get_market_snapshot", "blocked": False}],
            steps_remaining=1,
            final_answer_present=False,
        )

        self.assertEqual(result["decision"], "WARN")
        self.assertIn("budget", result["reason"].lower())

    def test_allows_healthy_short_trajectory(self) -> None:
        result = regulate_trajectory(
            history=[
                {"event": "tool", "tool_name": "get_market_snapshot", "blocked": False},
                {"event": "tool", "tool_name": "get_position", "blocked": False},
            ],
            steps_remaining=5,
            final_answer_present=False,
        )

        self.assertEqual(result["decision"], "ALLOW")

    def test_dynamic_trajectory_rule_can_warn_on_repeat_tool(self) -> None:
        original = os.environ.get("ACTIVE_TRAJECTORY_RULES_ARTIFACT_PATH")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                path = os.path.join(temp_dir, "trajectory_rules.json")
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(
                        {
                            "rules": [
                                {
                                    "rule_id": "repeat-balance",
                                    "pattern_type": "repeat_tool",
                                    "window": 3,
                                    "threshold": 3,
                                    "decision": "WARN",
                                    "message": "Dynamic repeat tool warning.",
                                    "watched_tools": ["get_balance"],
                                }
                            ]
                        },
                        handle,
                    )
                os.environ["ACTIVE_TRAJECTORY_RULES_ARTIFACT_PATH"] = path
                result = regulate_trajectory(
                    history=[
                        {"event": "tool", "tool_name": "get_balance", "blocked": False},
                        {"event": "tool", "tool_name": "get_balance", "blocked": False},
                        {"event": "tool", "tool_name": "get_balance", "blocked": False},
                    ],
                    steps_remaining=5,
                    final_answer_present=False,
                )
        finally:
            if original is None:
                os.environ.pop("ACTIVE_TRAJECTORY_RULES_ARTIFACT_PATH", None)
            else:
                os.environ["ACTIVE_TRAJECTORY_RULES_ARTIFACT_PATH"] = original

        self.assertEqual(result["decision"], "WARN")
        self.assertIn("Dynamic repeat tool warning.", result["reason"])


class TrajectoryRuntimeHelpersTests(unittest.TestCase):
    def test_build_trajectory_warning_feedback_contains_reason(self) -> None:
        feedback = build_trajectory_warning_feedback(
            {
                "decision": "WARN",
                "reason": "Agent is repeating the same tool too often: get_balance",
                "details": {},
            }
        )

        self.assertIn("Trajectory warning", feedback)
        self.assertIn("get_balance", feedback)

    def test_build_trajectory_stop_summary_contains_reason(self) -> None:
        summary = build_trajectory_stop_summary(
            {
                "decision": "STOP",
                "reason": "Repeated blocked action detected: same invalid close request",
                "details": {},
            }
        )

        self.assertIn("trajectory_regulation_stop", summary)
        self.assertIn("Repeated blocked action detected", summary)


class ProceduralSkillPromptingTests(unittest.TestCase):
    def test_skill_library_contains_entry_execution_skills(self) -> None:
        skills = get_skill_library()

        self.assertGreaterEqual(len(skills), 2)
        self.assertTrue(any("entry" in str(skill["title"]).lower() for skill in skills))

    def test_render_relevant_skills_block_formats_skill_content(self) -> None:
        block = render_relevant_skills_block(
            [
                {
                    "skill_id": "entry_confirm",
                    "title": "Entry confirmation sequence",
                    "tags": ["entry", "btc"],
                    "when_to_use": "Before opening a new position.",
                    "procedure": "Inspect market, position, and balance before entry.",
                    "anti_patterns": "Do not jump straight to open_long.",
                }
            ]
        )

        self.assertIn("Relevant Skills:", block)
        self.assertIn("Entry confirmation sequence", block)
        self.assertIn("When to use:", block)
        self.assertIn("Anti-patterns:", block)


class ProceduralSkillRetrievalTests(unittest.TestCase):
    def test_bm25_retrieval_prefers_entry_skill_for_open_long_query(self) -> None:
        results = retrieve_relevant_skills(
            query=(
                "user wants to open_long BTCUSDT after market inspection. "
                "Need entry execution guidance, inspect position and balance first."
            ),
            top_k=2,
        )

        self.assertGreaterEqual(len(results), 1)
        self.assertTrue(any("entry" in str(item["title"]).lower() for item in results))

    def test_bm25_retrieval_limits_results_to_top_k(self) -> None:
        results = retrieve_relevant_skills(
            query="entry execution for btcusdt",
            top_k=1,
        )

        self.assertEqual(len(results), 1)


class ProceduralSkillRuntimeIntegrationTests(unittest.TestCase):
    def test_build_skill_query_includes_task_state_and_tool_intent(self) -> None:
        query = build_skill_query(
            user_task="Inspect state then decide whether to open a position.",
            symbol="BTCUSDT",
            interval="1m",
            market_snapshot={"price": 63180.0},
            position_state={"side": "FLAT"},
            tool_intent="open_long",
        )

        self.assertIn("Inspect state then decide", query)
        self.assertIn("BTCUSDT", query)
        self.assertIn("open_long", query)
        self.assertIn('"price": 63180.0', query)


class ActionRealizationGateTests(unittest.TestCase):
    def test_blocks_close_position_when_state_is_flat(self) -> None:
        result = realize_action(
            tool_name="close_position",
            arguments={"symbol": "BTCUSDT"},
            position_state={"side": "FLAT", "is_open": False},
            inspected_state={
                "market_snapshot": True,
                "position": True,
                "balance": True,
            },
        )

        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("No open position", result["reason"])

    def test_blocks_open_long_when_position_is_already_open(self) -> None:
        result = realize_action(
            tool_name="open_long",
            arguments={"symbol": "BTCUSDT"},
            position_state={"side": "LONG", "is_open": True},
            inspected_state={
                "market_snapshot": True,
                "position": True,
                "balance": True,
            },
        )

        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("already open", result["reason"])

    def test_blocks_execution_when_required_state_was_not_inspected(self) -> None:
        result = realize_action(
            tool_name="open_short",
            arguments={"symbol": "BTCUSDT"},
            position_state={"side": "FLAT", "is_open": False},
            inspected_state={
                "market_snapshot": True,
                "position": False,
                "balance": True,
            },
        )

        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("position", result["reason"].lower())

    def test_allows_open_long_when_state_is_flat_and_fully_inspected(self) -> None:
        result = realize_action(
            tool_name="open_long",
            arguments={"symbol": "BTCUSDT"},
            position_state={"side": "FLAT", "is_open": False},
            inspected_state={
                "market_snapshot": True,
                "position": True,
                "balance": True,
            },
        )

        self.assertEqual(result["decision"], "EXECUTE")

    def test_dynamic_action_rule_can_block_matching_execution(self) -> None:
        original = os.environ.get("ACTIVE_ACTION_RULES_ARTIFACT_PATH")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                path = os.path.join(temp_dir, "action_rules.json")
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(
                        {
                            "rules": [
                                {
                                    "rule_id": "block-flat-open-long",
                                    "tool_name": "open_long",
                                    "condition": {"kind": "is_open", "value": False},
                                    "decision": "BLOCK",
                                    "message": "Dynamic action rule blocked this entry.",
                                }
                            ]
                        },
                        handle,
                    )
                os.environ["ACTIVE_ACTION_RULES_ARTIFACT_PATH"] = path
                result = realize_action(
                    tool_name="open_long",
                    arguments={"symbol": "BTCUSDT"},
                    position_state={"side": "FLAT", "is_open": False},
                    inspected_state={
                        "market_snapshot": True,
                        "position": True,
                        "balance": True,
                    },
                )
        finally:
            if original is None:
                os.environ.pop("ACTIVE_ACTION_RULES_ARTIFACT_PATH", None)
            else:
                os.environ["ACTIVE_ACTION_RULES_ARTIFACT_PATH"] = original

        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("Dynamic action rule blocked this entry.", result["reason"])


if __name__ == "__main__":
    unittest.main()
