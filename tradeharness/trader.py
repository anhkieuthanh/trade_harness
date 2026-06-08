from __future__ import annotations

import math

from tradeharness.models import Decision, Position, SymbolFilters


def floor_to_step(value: float, step: float) -> float:
    precision = int(round(-math.log10(step), 0)) if step < 1 else 0
    floored = math.floor(value / step) * step
    return round(floored, precision)


def calculate_order_quantity(
    balance_usdt: float,
    trade_size_percent: float,
    price: float,
    filters: SymbolFilters,
) -> float:
    notional = balance_usdt * (trade_size_percent / 100.0)
    raw_quantity = notional / price
    quantity = floor_to_step(raw_quantity, filters.step_size)
    if quantity < filters.min_qty:
        raise ValueError("Calculated quantity is below exchange minimum.")
    return quantity


def map_decision_to_order(
    decision: Decision,
    position: Position,
) -> tuple[str, str, bool] | None:
    if decision.action == "HOLD":
        return None
    if decision.action == "BUY" and not position.is_open:
        return ("BUY", "open_long", False)
    if decision.action == "SELL" and not position.is_open:
        return ("SELL", "open_short", False)
    if decision.action == "CLOSE" and position.is_open:
        side = "SELL" if position.quantity > 0 else "BUY"
        return (side, "close_position", True)
    return None
