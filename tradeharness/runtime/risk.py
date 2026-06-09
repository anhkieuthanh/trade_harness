from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LiveRiskControl:
    max_daily_loss_usdt: float = 50.0
    max_open_positions: int = 1
    loss_cooldown_seconds: int = 1800
    hard_stop_candle_range_pct: float = 2.0


@dataclass(frozen=True)
class LiveRiskRuntimeState:
    session_day: str | None = None
    day_start_balance_usdt: float | None = None
    last_loss_at: str | None = None
    last_loss_pnl_usdt: float | None = None
    hard_stop_reason: str | None = None
    hard_stop_at: str | None = None


@dataclass(frozen=True)
class LiveRiskDecision:
    decision: str
    reason: str
    daily_loss_usdt: float | None = None
    current_position_count: int | None = None
    candle_range_pct: float | None = None


def load_live_risk_state(path: Path) -> LiveRiskRuntimeState:
    if not path.exists():
        return LiveRiskRuntimeState()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return LiveRiskRuntimeState()
    if not isinstance(payload, dict):
        return LiveRiskRuntimeState()
    return LiveRiskRuntimeState(
        session_day=str(payload["session_day"]) if payload.get("session_day") else None,
        day_start_balance_usdt=(
            float(payload["day_start_balance_usdt"])
            if payload.get("day_start_balance_usdt") is not None
            else None
        ),
        last_loss_at=str(payload["last_loss_at"]) if payload.get("last_loss_at") else None,
        last_loss_pnl_usdt=(
            float(payload["last_loss_pnl_usdt"])
            if payload.get("last_loss_pnl_usdt") is not None
            else None
        ),
        hard_stop_reason=str(payload["hard_stop_reason"]) if payload.get("hard_stop_reason") else None,
        hard_stop_at=str(payload["hard_stop_at"]) if payload.get("hard_stop_at") else None,
    )


def save_live_risk_state(path: Path, state: LiveRiskRuntimeState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(state), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _candle_range_pct(market_snapshot: dict[str, Any]) -> float | None:
    candles = market_snapshot.get("candles")
    if not isinstance(candles, list) or not candles:
        return None
    last_candle = candles[-1]
    if not isinstance(last_candle, dict):
        return None
    try:
        high = float(last_candle["high"])
        low = float(last_candle["low"])
        close = float(last_candle["close"])
    except (KeyError, TypeError, ValueError):
        return None
    if close <= 0:
        return None
    return ((high - low) / close) * 100.0


def _position_count(position_state: dict[str, Any]) -> int:
    return 1 if bool(position_state.get("is_open", False)) else 0


def _is_opening_action(action: str | None) -> bool:
    return action in {"open_long", "open_short"}


def ensure_daily_baseline(
    runtime_state: LiveRiskRuntimeState,
    *,
    now: datetime,
    current_balance_usdt: float,
) -> LiveRiskRuntimeState:
    today = now.date().isoformat()
    if runtime_state.session_day == today and runtime_state.day_start_balance_usdt is not None:
        return runtime_state
    return LiveRiskRuntimeState(
        session_day=today,
        day_start_balance_usdt=current_balance_usdt,
        last_loss_at=None,
        last_loss_pnl_usdt=runtime_state.last_loss_pnl_usdt,
        hard_stop_reason=None,
        hard_stop_at=None,
    )


def evaluate_live_risk(
    *,
    control: LiveRiskControl,
    runtime_state: LiveRiskRuntimeState,
    market_snapshot: dict[str, Any],
    position_state: dict[str, Any],
    current_balance_usdt: float,
    planned_action: str,
    now: datetime | None,
) -> tuple[LiveRiskDecision, LiveRiskRuntimeState]:
    current_time = now or datetime.now(timezone.utc)
    normalized_state = ensure_daily_baseline(
        runtime_state,
        now=current_time,
        current_balance_usdt=current_balance_usdt,
    )
    daily_loss_usdt = 0.0
    if normalized_state.day_start_balance_usdt is not None:
        daily_loss_usdt = max(0.0, normalized_state.day_start_balance_usdt - current_balance_usdt)
    position_count = _position_count(position_state)
    candle_range_pct = _candle_range_pct(market_snapshot)

    def hard_stop(reason: str) -> tuple[LiveRiskDecision, LiveRiskRuntimeState]:
        updated = LiveRiskRuntimeState(
            session_day=normalized_state.session_day,
            day_start_balance_usdt=normalized_state.day_start_balance_usdt,
            last_loss_at=normalized_state.last_loss_at,
            last_loss_pnl_usdt=normalized_state.last_loss_pnl_usdt,
            hard_stop_reason=reason,
            hard_stop_at=current_time.isoformat(),
        )
        return (
            LiveRiskDecision(
                decision="FORCE_CLOSE" if position_count > 0 else "BLOCK",
                reason=reason,
                daily_loss_usdt=daily_loss_usdt,
                current_position_count=position_count,
                candle_range_pct=candle_range_pct,
            ),
            updated,
        )

    if control.max_daily_loss_usdt > 0 and daily_loss_usdt >= control.max_daily_loss_usdt:
        return hard_stop(
            f"daily loss limit reached ({daily_loss_usdt:.2f} >= {control.max_daily_loss_usdt:.2f} USDT)"
        )

    if (
        control.hard_stop_candle_range_pct > 0
        and candle_range_pct is not None
        and candle_range_pct >= control.hard_stop_candle_range_pct
    ):
        return hard_stop(
            f"market volatility too high ({candle_range_pct:.2f}% >= {control.hard_stop_candle_range_pct:.2f}%)"
        )

    if control.max_open_positions >= 0 and position_count > control.max_open_positions:
        return hard_stop(
            f"open positions above limit ({position_count} > {control.max_open_positions})"
        )

    if (
        control.max_open_positions >= 0
        and _is_opening_action(planned_action)
        and position_count >= control.max_open_positions
    ):
        return (
            LiveRiskDecision(
                decision="BLOCK",
                reason=(
                    f"max open positions reached ({position_count} >= {control.max_open_positions})"
                ),
                daily_loss_usdt=daily_loss_usdt,
                current_position_count=position_count,
                candle_range_pct=candle_range_pct,
            ),
            normalized_state,
        )

    if _is_opening_action(planned_action) and normalized_state.last_loss_at:
        last_loss_at = _parse_iso(normalized_state.last_loss_at)
        if last_loss_at is not None:
            elapsed = (current_time - last_loss_at).total_seconds()
            if control.loss_cooldown_seconds > 0 and elapsed < control.loss_cooldown_seconds:
                return (
                    LiveRiskDecision(
                        decision="BLOCK",
                        reason=(
                            f"loss cooldown active ({int(elapsed)}s < {control.loss_cooldown_seconds}s)"
                        ),
                        daily_loss_usdt=daily_loss_usdt,
                        current_position_count=position_count,
                        candle_range_pct=candle_range_pct,
                    ),
                    normalized_state,
                )

    return (
        LiveRiskDecision(
            decision="ALLOW",
            reason="risk guard clear",
            daily_loss_usdt=daily_loss_usdt,
            current_position_count=position_count,
            candle_range_pct=candle_range_pct,
        ),
        normalized_state,
    )


def record_trade_close(
    runtime_state: LiveRiskRuntimeState,
    *,
    position_state: dict[str, Any],
    exit_price: float,
    now: datetime,
) -> LiveRiskRuntimeState:
    try:
        quantity = float(position_state.get("quantity", 0.0))
        entry_price = float(position_state.get("entry_price", 0.0))
    except (TypeError, ValueError):
        return runtime_state
    if quantity == 0.0 or entry_price <= 0.0 or exit_price <= 0.0:
        return runtime_state

    if quantity > 0:
        pnl_usdt = (exit_price - entry_price) * quantity
    else:
        pnl_usdt = (entry_price - exit_price) * abs(quantity)

    if pnl_usdt < 0:
        return LiveRiskRuntimeState(
            session_day=runtime_state.session_day,
            day_start_balance_usdt=runtime_state.day_start_balance_usdt,
            last_loss_at=now.isoformat(),
            last_loss_pnl_usdt=pnl_usdt,
            hard_stop_reason=runtime_state.hard_stop_reason,
            hard_stop_at=runtime_state.hard_stop_at,
        )

    return LiveRiskRuntimeState(
        session_day=runtime_state.session_day,
        day_start_balance_usdt=runtime_state.day_start_balance_usdt,
        last_loss_at=runtime_state.last_loss_at,
        last_loss_pnl_usdt=pnl_usdt,
        hard_stop_reason=runtime_state.hard_stop_reason,
        hard_stop_at=runtime_state.hard_stop_at,
    )
