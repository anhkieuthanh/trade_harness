from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from tradeharness.runtime.strategy import (
    RandomFlipPlan,
    RandomFlipState,
    build_random_flip_plan,
    load_random_flip_state,
    save_random_flip_state,
)
from tradeharness.runtime.strategies import get_trade_strategy


class RandomFlipStrategyTests(unittest.TestCase):
    def test_build_random_flip_plan_opens_random_side_when_flat(self) -> None:
        plan = build_random_flip_plan(
            position_state={"is_open": False},
            strategy_state=RandomFlipState(),
            now=datetime(2026, 6, 9, 1, 0, tzinfo=timezone.utc),
            hold_seconds=120,
            choose_side=lambda: "open_short",
        )

        self.assertEqual(plan.action, "open_short")
        self.assertEqual(plan.reason, "flat position, opening random side")

    def test_build_random_flip_plan_holds_before_timeout(self) -> None:
        plan = build_random_flip_plan(
            position_state={"is_open": True},
            strategy_state=RandomFlipState(opened_at="2026-06-09T01:00:00+00:00"),
            now=datetime(2026, 6, 9, 1, 1, 30, tzinfo=timezone.utc),
            hold_seconds=120,
            choose_side=lambda: "open_long",
        )

        self.assertEqual(plan.action, "hold")
        self.assertEqual(plan.reason, "hold window still active")

    def test_build_random_flip_plan_closes_after_timeout(self) -> None:
        plan = build_random_flip_plan(
            position_state={"is_open": True},
            strategy_state=RandomFlipState(opened_at="2026-06-09T01:00:00+00:00"),
            now=datetime(2026, 6, 9, 1, 2, 30, tzinfo=timezone.utc),
            hold_seconds=120,
            choose_side=lambda: "open_long",
        )

        self.assertEqual(plan.action, "close_position")
        self.assertEqual(plan.reason, "hold window expired")

    def test_build_random_flip_plan_holds_during_cooldown(self) -> None:
        plan = build_random_flip_plan(
            position_state={"is_open": False},
            strategy_state=RandomFlipState(last_closed_at="2026-06-09T01:00:00+00:00"),
            now=datetime(2026, 6, 9, 1, 0, 30, tzinfo=timezone.utc),
            hold_seconds=120,
            cooldown_seconds=60,
            choose_side=lambda: "open_long",
        )

        self.assertEqual(plan.action, "hold")
        self.assertEqual(plan.reason, "cooldown window still active")

    def test_strategy_state_round_trips_through_json_file(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            path = Path(temp_dir_name) / "strategy_state.json"
            state = RandomFlipState(
                opened_at="2026-06-09T01:00:00+00:00",
                side="LONG",
                quantity=0.008,
            )

            save_random_flip_state(path, state)
            loaded = load_random_flip_state(path)

        self.assertEqual(loaded, state)

    def test_strategy_registry_resolves_random_flip(self) -> None:
        strategy = get_trade_strategy("random_flip")

        self.assertEqual(strategy.name, "random_flip")


if __name__ == "__main__":
    unittest.main()
