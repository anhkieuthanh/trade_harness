from __future__ import annotations

import unittest
from datetime import datetime, timezone, timedelta

from tradeharness.runtime.risk import (
    LiveRiskControl,
    LiveRiskRuntimeState,
    evaluate_live_risk,
    record_trade_close,
)


class LiveRiskGuardTests(unittest.TestCase):
    def test_daily_loss_breach_forces_close_when_position_is_open(self) -> None:
        now = datetime(2026, 6, 9, 1, 0, tzinfo=timezone.utc)
        decision, updated_state = evaluate_live_risk(
            control=LiveRiskControl(max_daily_loss_usdt=10.0),
            runtime_state=LiveRiskRuntimeState(
                session_day="2026-06-09",
                day_start_balance_usdt=1000.0,
            ),
            market_snapshot={"candles": [{"high": 101.0, "low": 99.0, "close": 100.0}]},
            position_state={"is_open": True},
            current_balance_usdt=985.0,
            planned_action="open_long",
            now=now,
        )

        self.assertEqual(decision.decision, "FORCE_CLOSE")
        self.assertIn("daily loss limit reached", decision.reason)
        self.assertEqual(updated_state.hard_stop_reason, decision.reason)

    def test_loss_cooldown_blocks_new_entry_after_recent_loss(self) -> None:
        now = datetime(2026, 6, 9, 1, 0, tzinfo=timezone.utc)
        decision, _ = evaluate_live_risk(
            control=LiveRiskControl(loss_cooldown_seconds=300),
            runtime_state=LiveRiskRuntimeState(
                session_day="2026-06-09",
                day_start_balance_usdt=1000.0,
                last_loss_at=(now - timedelta(seconds=60)).isoformat(),
            ),
            market_snapshot={"candles": [{"high": 100.5, "low": 100.0, "close": 100.0}]},
            position_state={"is_open": False},
            current_balance_usdt=1000.0,
            planned_action="open_long",
            now=now,
        )

        self.assertEqual(decision.decision, "BLOCK")
        self.assertIn("loss cooldown active", decision.reason)

    def test_market_volatility_hard_stop_forces_close_when_position_is_open(self) -> None:
        now = datetime(2026, 6, 9, 1, 0, tzinfo=timezone.utc)
        decision, updated_state = evaluate_live_risk(
            control=LiveRiskControl(hard_stop_candle_range_pct=2.0),
            runtime_state=LiveRiskRuntimeState(
                session_day="2026-06-09",
                day_start_balance_usdt=1000.0,
            ),
            market_snapshot={"candles": [{"high": 104.0, "low": 100.0, "close": 100.0}]},
            position_state={"is_open": True},
            current_balance_usdt=1000.0,
            planned_action="hold",
            now=now,
        )

        self.assertEqual(decision.decision, "FORCE_CLOSE")
        self.assertIn("market volatility too high", decision.reason)
        self.assertEqual(updated_state.hard_stop_reason, decision.reason)

    def test_record_trade_close_marks_last_loss_when_trade_is_negative(self) -> None:
        now = datetime(2026, 6, 9, 1, 0, tzinfo=timezone.utc)
        updated_state = record_trade_close(
            LiveRiskRuntimeState(session_day="2026-06-09", day_start_balance_usdt=1000.0),
            position_state={"quantity": 1.0, "entry_price": 100.0},
            exit_price=95.0,
            now=now,
        )

        self.assertEqual(updated_state.last_loss_at, now.isoformat())
        self.assertLess(updated_state.last_loss_pnl_usdt or 0.0, 0.0)


if __name__ == "__main__":
    unittest.main()
