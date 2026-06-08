from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


Action = Literal["BUY", "SELL", "HOLD", "CLOSE"]


@dataclass(frozen=True)
class Candle:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: float
    entry_price: float

    @property
    def is_open(self) -> bool:
        return self.quantity != 0.0

    @property
    def side(self) -> str:
        if self.quantity > 0:
            return "LONG"
        if self.quantity < 0:
            return "SHORT"
        return "FLAT"


@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str


@dataclass(frozen=True)
class SymbolFilters:
    step_size: float
    min_qty: float


@dataclass(frozen=True)
class ToolRequest:
    name: str
    arguments: dict[str, Any]
    call_id: str | None = None
