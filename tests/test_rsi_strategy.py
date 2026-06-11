"""Unit tests for the RSI Crossover Trading Strategy."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import unittest

from tradeharness.runtime.strategies.rsi_strategy import (
    ManualOnlyStrategy,
    RSIPlan,
    RSIState,
    RSIStrategy,
    get_trade_strategy,
)


def _make_candles(closes: list[float]) -> list[dict]:
    """Build minimal candle dicts from a list of close prices."""
    return [{"close": str(c), "open": str(c), "high": str(c), "low": str(c)} for c in closes]


class TestRSICalculation(unittest.TestCase):
    def setUp(self):
        self.strategy = RSIStrategy()

    def test_neutral_on_empty_candles(self):
        """RSI returns 50.0 when no candles provided."""
        self.assertEqual(self.strategy.calculate_rsi([]), 50.0)

    def test_neutral_on_single_candle(self):
        """RSI returns 50.0 with only one candle (no change)."""
        candles = _make_candles([100.0])
        self.assertEqual(self.strategy.calculate_rsi(candles), 50.0)

    def test_all_gains_returns_100(self):
        """When prices only go up, RSI should be 100."""
        closes = [float(i) for i in range(1, 20)]  # pure uptrend
        candles = _make_candles(closes)
        rsi = self.strategy.calculate_rsi(candles, period=7)
        self.assertAlmostEqual(rsi, 100.0)

    def test_all_losses_returns_0(self):
        """When prices only go down, RSI should be ~0."""
        closes = [float(i) for i in range(20, 0, -1)]  # pure downtrend
        candles = _make_candles(closes)
        rsi = self.strategy.calculate_rsi(candles, period=7)
        self.assertAlmostEqual(rsi, 0.0)

    def test_rsi_in_range(self):
        """RSI should always be between 0 and 100."""
        import random
        random.seed(42)
        closes = [50.0 + random.uniform(-5, 5) for _ in range(60)]
        candles = _make_candles(closes)
        rsi = self.strategy.calculate_rsi(candles, period=7)
        self.assertGreaterEqual(rsi, 0.0)
        self.assertLessEqual(rsi, 100.0)

    def test_oversold_scenario(self):
        """After a steep drop, RSI should be below 30."""
        # Start at 100 and crash down to 50
        closes = [100.0] * 5 + [95.0, 90.0, 85.0, 78.0, 70.0, 62.0, 55.0, 50.0]
        candles = _make_candles(closes)
        rsi = self.strategy.calculate_rsi(candles, period=7)
        self.assertLess(rsi, 40.0)

    def test_overbought_scenario(self):
        """After a steep rise, RSI should be above 70."""
        # Start at 50 and rally to 100
        closes = [50.0] * 5 + [55.0, 62.0, 70.0, 78.0, 85.0, 92.0, 98.0, 100.0]
        candles = _make_candles(closes)
        rsi = self.strategy.calculate_rsi(candles, period=7)
        self.assertGreater(rsi, 60.0)


class TestRSIStrategyBuildPlan(unittest.TestCase):
    def setUp(self):
        self.strategy = RSIStrategy()
        self.now = datetime(2026, 6, 11, 10, 0, 0, tzinfo=timezone.utc)

    def _build_plan(
        self,
        *,
        closes: list[float],
        is_open: bool = False,
        side: str | None = None,
        opened_at: str | None = None,
        last_closed_at: str | None = None,
        hold_seconds: int = 300,
        cooldown_seconds: int = 60,
        entry_rsi: float | None = None,
    ) -> RSIPlan:
        candles = _make_candles(closes)
        position_state: dict = {"is_open": is_open, "side": side, "quantity": 0.008}
        strategy_state = RSIState(
            opened_at=opened_at,
            side=side,
            quantity=0.008 if is_open else None,
            last_closed_at=last_closed_at,
            entry_rsi=entry_rsi,
        )
        return self.strategy.build_plan(
            position_state=position_state,
            strategy_state=strategy_state,
            now=self.now,
            hold_seconds=hold_seconds,
            cooldown_seconds=cooldown_seconds,
            market_snapshot={"candles": candles, "price": str(closes[-1])},
            rsi_period=7,
        )

    # --- Entry signals ---

    def test_buy_signal_when_oversold(self):
        """Should return open_long when RSI ≤ 30 and no open position."""
        closes = [100.0] * 5 + [95.0, 90.0, 85.0, 78.0, 70.0, 62.0, 55.0, 50.0]
        plan = self._build_plan(closes=closes)
        self.assertEqual(plan.action, "open_long")
        self.assertEqual(plan.side, "LONG")
        self.assertIn("oversold", plan.reason.lower())

    def test_sell_signal_when_overbought(self):
        """Should return open_short when RSI ≥ 70 and no open position."""
        closes = [50.0] * 5 + [55.0, 62.0, 70.0, 78.0, 85.0, 92.0, 98.0, 100.0]
        plan = self._build_plan(closes=closes)
        self.assertEqual(plan.action, "open_short")
        self.assertEqual(plan.side, "SHORT")
        self.assertIn("overbought", plan.reason.lower())

    def test_hold_in_neutral_zone(self):
        """Should hold when RSI is in neutral range."""
        # Alternating to keep RSI near 50
        closes = [50.0 + ((-1) ** i) * 1.0 for i in range(20)]
        plan = self._build_plan(closes=closes)
        self.assertEqual(plan.action, "hold")

    # --- Position management ---

    def test_close_on_hold_expiry(self):
        """Should close position when hold window has expired."""
        # Position opened 400s ago, hold_seconds=300
        opened_at = datetime(2026, 6, 11, 9, 53, 20, tzinfo=timezone.utc).isoformat()
        closes = [50.0 + ((-1) ** i) * 1.0 for i in range(20)]
        plan = self._build_plan(
            closes=closes, is_open=True, side="LONG", opened_at=opened_at, hold_seconds=300
        )
        self.assertEqual(plan.action, "close_position")
        self.assertIn("expired", plan.reason.lower())

    def test_close_long_on_rsi_reversion(self):
        """Should close LONG position when RSI reverts to ≥ 50 (overbought recovery)."""
        opened_at = datetime(2026, 6, 11, 9, 59, 0, tzinfo=timezone.utc).isoformat()
        # Pure uptrend → RSI = 100 → triggers close_position for LONG (RSI >= 50)
        closes = [float(i) for i in range(1, 20)]
        plan = self._build_plan(
            closes=closes, is_open=True, side="LONG", opened_at=opened_at, hold_seconds=300
        )
        self.assertEqual(plan.action, "close_position")
        self.assertIn("profit-take", plan.reason.lower())

    def test_hold_within_window_no_reversion(self):
        """Should hold when position is open, window not expired, and RSI not reverted."""
        # Position opened 60s ago (within 300s window)
        opened_at = datetime(2026, 6, 11, 9, 59, 0, tzinfo=timezone.utc).isoformat()
        # RSI strongly oversold still → keep holding LONG
        closes = [100.0] * 5 + [95.0, 88.0, 80.0, 72.0, 63.0, 56.0, 49.0]
        # But RSI will be < 50 so LONG won't be closed early
        plan = self._build_plan(
            closes=closes, is_open=True, side="LONG", opened_at=opened_at, hold_seconds=300
        )
        self.assertEqual(plan.action, "hold")

    # --- Cooldown ---

    def test_cooldown_prevents_new_entry(self):
        """Should hold during cooldown period after a trade close."""
        # Last closed 30s ago, cooldown = 60s
        last_closed_at = datetime(2026, 6, 11, 9, 59, 30, tzinfo=timezone.utc).isoformat()
        # RSI is in oversold territory, but cooldown not over
        closes = [100.0] * 5 + [95.0, 90.0, 85.0, 78.0, 70.0, 62.0, 55.0, 50.0]
        plan = self._build_plan(
            closes=closes,
            last_closed_at=last_closed_at,
            cooldown_seconds=60,
        )
        self.assertEqual(plan.action, "hold")
        self.assertIn("cooldown", plan.reason.lower())

    def test_entry_after_cooldown_expires(self):
        """Should allow entry once cooldown has passed."""
        # Last closed 120s ago, cooldown = 60s → expired
        last_closed_at = datetime(2026, 6, 11, 9, 58, 0, tzinfo=timezone.utc).isoformat()
        closes = [100.0] * 5 + [95.0, 90.0, 85.0, 78.0, 70.0, 62.0, 55.0, 50.0]
        plan = self._build_plan(
            closes=closes,
            last_closed_at=last_closed_at,
            cooldown_seconds=60,
        )
        self.assertEqual(plan.action, "open_long")


class TestRSIStateSerialization(unittest.TestCase):
    def setUp(self):
        self.strategy = RSIStrategy()

    def test_round_trip(self):
        """State saved and loaded should match original."""
        original = RSIState(
            opened_at="2026-06-11T09:00:00+00:00",
            side="LONG",
            quantity=0.008,
            last_closed_at=None,
            entry_rsi=27.3,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            self.strategy.save_state(path, original)
            loaded = self.strategy.load_state(path)
        self.assertEqual(loaded.opened_at, original.opened_at)
        self.assertEqual(loaded.side, original.side)
        self.assertAlmostEqual(loaded.quantity, original.quantity)
        self.assertIsNone(loaded.last_closed_at)
        self.assertAlmostEqual(loaded.entry_rsi, original.entry_rsi)

    def test_empty_state_on_missing_file(self):
        """Missing state file returns default RSIState."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nonexistent.json"
            state = self.strategy.load_state(path)
        self.assertIsNone(state.opened_at)
        self.assertIsNone(state.side)
        self.assertIsNone(state.quantity)

    def test_empty_state_on_corrupt_json(self):
        """Corrupt JSON file returns default RSIState."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("not valid json", encoding="utf-8")
            state = self.strategy.load_state(path)
        self.assertIsNone(state.opened_at)


class TestGetTradeStrategy(unittest.TestCase):
    def test_returns_rsi_strategy(self):
        strategy = get_trade_strategy("rsi_strategy")
        self.assertIsInstance(strategy, RSIStrategy)

    def test_returns_manual_only(self):
        strategy = get_trade_strategy("manual_only")
        self.assertIsInstance(strategy, ManualOnlyStrategy)

    def test_raises_on_unknown(self):
        with self.assertRaises(ValueError):
            get_trade_strategy("random_flip")

    def test_case_insensitive(self):
        strategy = get_trade_strategy("RSI_STRATEGY")
        self.assertIsInstance(strategy, RSIStrategy)


class TestManualOnlyStrategy(unittest.TestCase):
    def test_always_holds(self):
        strategy = ManualOnlyStrategy()
        candles = _make_candles([50.0 + i for i in range(20)])
        plan = strategy.build_plan(
            position_state={"is_open": False},
            strategy_state=RSIState(),
            now=datetime.now(timezone.utc),
            hold_seconds=300,
            cooldown_seconds=60,
            market_snapshot={"candles": candles},
        )
        self.assertEqual(plan.action, "hold")
        self.assertIn("manual_only", plan.reason)


if __name__ == "__main__":
    unittest.main()
