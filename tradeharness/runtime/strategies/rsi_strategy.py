from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RSIState:
    opened_at: str | None = None
    side: str | None = None
    quantity: float | None = None
    last_closed_at: str | None = None
    entry_rsi: float | None = None


@dataclass(frozen=True)
class RSIPlan:
    action: str
    reason: str
    side: str | None = None


class RSIStrategy:
    name = "rsi_strategy"

    def load_state(self, path: Path) -> RSIState:
        if not path.exists():
            return RSIState()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return RSIState()
        if not isinstance(payload, dict):
            return RSIState()
        return RSIState(
            opened_at=str(payload["opened_at"]) if payload.get("opened_at") else None,
            side=str(payload["side"]) if payload.get("side") else None,
            quantity=float(payload["quantity"]) if payload.get("quantity") is not None else None,
            last_closed_at=str(payload["last_closed_at"]) if payload.get("last_closed_at") else None,
            entry_rsi=float(payload["entry_rsi"]) if payload.get("entry_rsi") is not None else None,
        )

    def save_state(self, path: Path, state: RSIState) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(state), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def calculate_rsi(self, candles: list[dict[str, Any]], period: int = 14) -> float:
        if len(candles) < 2:
            return 50.0  # Neutral default
        
        closes = [float(c["close"]) for c in candles if "close" in c]
        if len(closes) < 2:
            return 50.0

        changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = [val if val > 0 else 0.0 for val in changes]
        losses = [-val if val < 0 else 0.0 for val in changes]
        
        actual_period = min(period, len(changes))
        if actual_period == 0:
            return 50.0

        avg_gain = sum(gains[:actual_period]) / actual_period
        avg_loss = sum(losses[:actual_period]) / actual_period
        
        for i in range(actual_period, len(changes)):
            avg_gain = (avg_gain * (actual_period - 1) + gains[i]) / actual_period
            avg_loss = (avg_loss * (actual_period - 1) + losses[i]) / actual_period
            
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
            
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def build_plan(
        self,
        *,
        position_state: dict[str, object],
        strategy_state: RSIState,
        now: datetime | None,
        hold_seconds: int,
        cooldown_seconds: int,
        market_snapshot: dict[str, Any],
        rsi_period: int = 7,
        oversold_threshold: float = 30.0,
        overbought_threshold: float = 70.0,
    ) -> RSIPlan:
        current_time = now or datetime.now(timezone.utc)
        is_open = bool(position_state.get("is_open", False))
        
        # Calculate RSI
        candles = market_snapshot.get("candles", [])
        rsi = self.calculate_rsi(candles, period=rsi_period)

        if is_open:
            opened_at = self._parse_iso(strategy_state.opened_at)
            if opened_at is None:
                return RSIPlan(
                    action="hold",
                    reason=f"position open (RSI: {rsi:.1f}), but hold start time is unknown",
                )
            elapsed_seconds = (current_time - opened_at).total_seconds()
            
            # Exit rules: time elapsed, or RSI reverted to neutral range
            if elapsed_seconds >= hold_seconds:
                return RSIPlan(
                    action="close_position",
                    reason=f"hold window expired (elapsed: {elapsed_seconds:.0f}s >= {hold_seconds}s)",
                )
            
            # Exit on RSI reversion (e.g. crossing 50)
            if strategy_state.side == "LONG" and rsi >= 50.0:
                return RSIPlan(
                    action="close_position",
                    reason=f"RSI profit-take target met (RSI: {rsi:.1f} >= 50.0)",
                )
            elif strategy_state.side == "SHORT" and rsi <= 50.0:
                return RSIPlan(
                    action="close_position",
                    reason=f"RSI profit-take target met (RSI: {rsi:.1f} <= 50.0)",
                )
                
            return RSIPlan(
                action="hold",
                reason=f"position open (RSI: {rsi:.1f}), hold window active (elapsed: {elapsed_seconds:.0f}s)",
            )

        if cooldown_seconds > 0 and strategy_state.last_closed_at:
            last_closed_at = self._parse_iso(strategy_state.last_closed_at)
            if last_closed_at is not None:
                elapsed_since_close = (current_time - last_closed_at).total_seconds()
                if elapsed_since_close < cooldown_seconds:
                    return RSIPlan(
                        action="hold",
                        reason=f"cooldown window active (elapsed: {elapsed_since_close:.0f}s < {cooldown_seconds}s)",
                    )

        # Entry logic
        if rsi <= oversold_threshold:
            return RSIPlan(
                action="open_long",
                reason=f"RSI is oversold (RSI: {rsi:.1f} <= {oversold_threshold})",
                side="LONG",
            )
        elif rsi >= overbought_threshold:
            return RSIPlan(
                action="open_short",
                reason=f"RSI is overbought (RSI: {rsi:.1f} >= {overbought_threshold})",
                side="SHORT",
            )

        return RSIPlan(
            action="hold",
            reason=f"RSI in neutral range (RSI: {rsi:.1f})",
        )

    def _parse_iso(self, value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None


class ManualOnlyStrategy:
    name = "manual_only"

    def load_state(self, path: Path) -> RSIState:
        return RSIState()

    def save_state(self, path: Path, state: RSIState) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(state), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def build_plan(
        self,
        *,
        position_state: dict[str, object],
        strategy_state: RSIState,
        now: datetime | None,
        hold_seconds: int,
        cooldown_seconds: int,
        market_snapshot: dict[str, Any],
    ) -> RSIPlan:
        return RSIPlan(
            action="hold",
            reason="manual_only strategy selected",
        )


def get_trade_strategy(mode: str):
    normalized_mode = mode.strip().lower()
    if normalized_mode == "rsi_strategy":
        return RSIStrategy()
    if normalized_mode == "manual_only":
        return ManualOnlyStrategy()
    raise ValueError(f"Unsupported trade strategy mode: {mode}")
