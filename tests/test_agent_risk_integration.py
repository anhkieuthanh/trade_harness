from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from tradeharness.config.settings import load_settings
from tradeharness.runtime.agent import run_agent_cycle


class FakeBinanceClientForRisk:
    def __init__(self, side="FLAT", is_open=False, balance=1000.0) -> None:
        self._side = side
        self._is_open = is_open
        self._balance = balance
        self.calls = []

    def get_price(self, symbol: str) -> float:
        return 60000.0

    def get_klines(self, symbol: str, interval: str, limit: int):
        return []

    def get_available_balance(self, asset: str = "USDT") -> float:
        return self._balance

    def get_position(self, symbol: str):
        class Position:
            side = self._side
            quantity = 1.0 if self._is_open else 0.0
            entry_price = 60000.0 if self._is_open else 0.0
            is_open = self._is_open
        return Position()

    def get_symbol_filters(self, symbol: str):
        class Filters:
            step_size = 0.001
            min_qty = 0.001
        return Filters()

    def place_market_order(self, symbol: str, side: str, quantity: float, reduce_only: bool = False):
        self.calls.append(("place_market_order", (symbol, side, quantity, reduce_only)))
        return {"symbol": symbol, "side": side, "quantity": quantity, "reduceOnly": reduce_only}


class AgentRiskIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.trajectory_log = Path(self.temp_dir.name) / "episodes.jsonl"
        self.risk_state_path = Path(self.temp_dir.name) / "risk_state.json"
        
        # Load environment defaults to avoid KeyError on load_settings
        os.environ.setdefault("BINANCE_API_KEY", "dummy_key")
        os.environ.setdefault("BINANCE_API_SECRET", "dummy_secret")

        base_settings = load_settings()
        self.settings = replace(
            base_settings,
            symbol="BTCUSDT",
            candle_interval="1m",
            candle_limit=5,
            trade_strategy_mode="llm_agent",
            trade_size_percent=10.0,
            trade_entry_quantity_btc=0.01,
            trade_hold_seconds=60,
            trade_cooldown_seconds=60,
            trade_risk_max_daily_loss_usdt=50.0,
            trade_risk_max_open_positions=1,
            trade_risk_loss_cooldown_seconds=1800,
            trade_risk_hard_stop_candle_range_pct=2.0,
            trade_risk_state_path=str(self.risk_state_path),
            trajectory_log_path=str(self.trajectory_log),
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @patch("tradeharness.runtime.agent.BinanceFuturesTestnetClient")
    @patch("tradeharness.runtime.agent.LMStudioClient")
    def test_run_agent_cycle_blocks_when_daily_loss_limit_reached(self, mock_lmstudio_cls, mock_binance_cls) -> None:
        # Mock Binance client to simulate a high loss (start balance was 1000, current balance is 940 -> loss of 60 USDT, exceeds limit of 50)
        fake_binance = FakeBinanceClientForRisk(balance=940.0)
        mock_binance_cls.return_value = fake_binance

        # Prepare risk state with day_start_balance of 1000.0
        with open(self.risk_state_path, "w") as f:
            json.dump({
                "session_day": datetime.now(timezone.utc).date().isoformat(),
                "day_start_balance_usdt": 1000.0,
                "last_loss_at": None,
                "last_loss_pnl_usdt": None,
                "hard_stop_reason": None,
                "hard_stop_at": None
            }, f)

        # Mock LM Studio to request get_balance first, then repeatedly request open_long
        mock_lm = Mock()
        mock_lmstudio_cls.return_value = mock_lm
        
        # Turn 1: request get_balance
        response_1 = {
            "choices": [{
                "message": {
                    "content": "",
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "get_balance",
                            "arguments": '{"asset":"USDT"}'
                        }
                    }]
                }
            }]
        }
        # Turn 2-5: request open_long (to trigger maximum retries limit and force FAILED state)
        response_open = {
            "choices": [{
                "message": {
                    "content": "",
                    "tool_calls": [{
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "open_long",
                            "arguments": '{"symbol":"BTCUSDT"}'
                        }
                    }]
                }
            }]
        }
        
        mock_lm.complete.side_effect = [
            response_1,     # Turn 1: get_balance (ALLOW)
            response_open,  # Turn 2: open_long (risk BLOCK, count=1)
            response_open,  # Turn 3: open_long (risk BLOCK, count=2)
            response_open,  # Turn 4: open_long (risk BLOCK, count=3 -> terminates)
        ]

        # Run cycle
        run_agent_cycle(self.settings)

        # Verify order was not placed
        self.assertEqual(fake_binance.calls, [])

        # Check that the block is logged in the trajectory file
        self.assertTrue(self.trajectory_log.exists())
        with open(self.trajectory_log, "r") as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(record["final_status"], "FAILED")
            self.assertEqual(record["termination_reason"], "blocked_by_live_risk_limit")


if __name__ == "__main__":
    unittest.main()
