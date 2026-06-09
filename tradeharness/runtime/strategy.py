from __future__ import annotations

from tradeharness.runtime.strategies.random_flip import (
    RandomFlipPlan,
    RandomFlipState,
    RandomFlipStrategy,
)


def load_random_flip_state(path):
    return RandomFlipStrategy().load_state(path)


def save_random_flip_state(path, state):
    RandomFlipStrategy().save_state(path, state)


def build_random_flip_plan(
    *,
    position_state,
    strategy_state,
    now,
    hold_seconds,
    cooldown_seconds=0,
    choose_side,
):
    return RandomFlipStrategy().build_plan(
        position_state=position_state,
        strategy_state=strategy_state,
        now=now,
        hold_seconds=hold_seconds,
        cooldown_seconds=cooldown_seconds,
        choose_side=choose_side,
    )
