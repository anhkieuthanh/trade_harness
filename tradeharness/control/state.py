from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_OFFLINE_EVOLUTION_TIME = "01:00"
DEFAULT_STRATEGY_MODE = "random_flip"
DEFAULT_STRATEGY_ENTRY_QUANTITY_BTC = 0.008
DEFAULT_STRATEGY_HOLD_SECONDS = 120
DEFAULT_STRATEGY_COOLDOWN_SECONDS = 0
DEFAULT_RISK_MAX_DAILY_LOSS_USDT = 50.0
DEFAULT_RISK_MAX_OPEN_POSITIONS = 1
DEFAULT_RISK_LOSS_COOLDOWN_SECONDS = 1800
DEFAULT_RISK_HARD_STOP_CANDLE_RANGE_PCT = 2.0


@dataclass(frozen=True)
class StrategyControlState:
    mode: str = DEFAULT_STRATEGY_MODE
    entry_quantity_btc: float = DEFAULT_STRATEGY_ENTRY_QUANTITY_BTC
    hold_seconds: int = DEFAULT_STRATEGY_HOLD_SECONDS
    cooldown_seconds: int = DEFAULT_STRATEGY_COOLDOWN_SECONDS


@dataclass(frozen=True)
class RiskControlState:
    max_daily_loss_usdt: float = DEFAULT_RISK_MAX_DAILY_LOSS_USDT
    max_open_positions: int = DEFAULT_RISK_MAX_OPEN_POSITIONS
    loss_cooldown_seconds: int = DEFAULT_RISK_LOSS_COOLDOWN_SECONDS
    hard_stop_candle_range_pct: float = DEFAULT_RISK_HARD_STOP_CANDLE_RANGE_PCT


@dataclass(frozen=True)
class ControlState:
    live_enabled: bool = False
    offline_evolution_enabled: bool = True
    offline_evolution_time: str = DEFAULT_OFFLINE_EVOLUTION_TIME
    last_offline_evolution_run_date: str | None = None
    strategy: StrategyControlState = field(default_factory=StrategyControlState)
    risk: RiskControlState = field(default_factory=RiskControlState)


def _is_valid_time(value: str) -> bool:
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError:
        return False
    return True


def _normalize_time(value: Any) -> str:
    candidate = str(value or "").strip()
    if _is_valid_time(candidate):
        return candidate
    return DEFAULT_OFFLINE_EVOLUTION_TIME


def _normalize_strategy_state(value: Any) -> StrategyControlState:
    if isinstance(value, StrategyControlState):
        return value
    if not isinstance(value, dict):
        return StrategyControlState()
    mode = str(value.get("mode") or DEFAULT_STRATEGY_MODE).strip() or DEFAULT_STRATEGY_MODE
    try:
        entry_quantity_btc = float(value.get("entry_quantity_btc", DEFAULT_STRATEGY_ENTRY_QUANTITY_BTC))
    except (TypeError, ValueError):
        entry_quantity_btc = DEFAULT_STRATEGY_ENTRY_QUANTITY_BTC
    try:
        hold_seconds = int(value.get("hold_seconds", DEFAULT_STRATEGY_HOLD_SECONDS))
    except (TypeError, ValueError):
        hold_seconds = DEFAULT_STRATEGY_HOLD_SECONDS
    try:
        cooldown_seconds = int(value.get("cooldown_seconds", DEFAULT_STRATEGY_COOLDOWN_SECONDS))
    except (TypeError, ValueError):
        cooldown_seconds = DEFAULT_STRATEGY_COOLDOWN_SECONDS
    return StrategyControlState(
        mode=mode,
        entry_quantity_btc=entry_quantity_btc,
        hold_seconds=max(0, hold_seconds),
        cooldown_seconds=max(0, cooldown_seconds),
    )


def _normalize_risk_state(value: Any) -> RiskControlState:
    if isinstance(value, RiskControlState):
        return value
    if not isinstance(value, dict):
        return RiskControlState()
    try:
        max_daily_loss_usdt = float(value.get("max_daily_loss_usdt", DEFAULT_RISK_MAX_DAILY_LOSS_USDT))
    except (TypeError, ValueError):
        max_daily_loss_usdt = DEFAULT_RISK_MAX_DAILY_LOSS_USDT
    try:
        max_open_positions = int(value.get("max_open_positions", DEFAULT_RISK_MAX_OPEN_POSITIONS))
    except (TypeError, ValueError):
        max_open_positions = DEFAULT_RISK_MAX_OPEN_POSITIONS
    try:
        loss_cooldown_seconds = int(value.get("loss_cooldown_seconds", DEFAULT_RISK_LOSS_COOLDOWN_SECONDS))
    except (TypeError, ValueError):
        loss_cooldown_seconds = DEFAULT_RISK_LOSS_COOLDOWN_SECONDS
    try:
        hard_stop_candle_range_pct = float(
            value.get("hard_stop_candle_range_pct", DEFAULT_RISK_HARD_STOP_CANDLE_RANGE_PCT)
        )
    except (TypeError, ValueError):
        hard_stop_candle_range_pct = DEFAULT_RISK_HARD_STOP_CANDLE_RANGE_PCT
    return RiskControlState(
        max_daily_loss_usdt=max(0.0, max_daily_loss_usdt),
        max_open_positions=max(0, max_open_positions),
        loss_cooldown_seconds=max(0, loss_cooldown_seconds),
        hard_stop_candle_range_pct=max(0.0, hard_stop_candle_range_pct),
    )


def load_control_state(path: Path) -> ControlState:
    if not path.exists():
        return ControlState()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ControlState()
    if not isinstance(payload, dict):
        return ControlState()

    last_run = payload.get("last_offline_evolution_run_date")
    if last_run is not None:
        last_run = str(last_run)

    return ControlState(
        live_enabled=bool(payload.get("live_enabled", False)),
        offline_evolution_enabled=bool(payload.get("offline_evolution_enabled", True)),
        offline_evolution_time=_normalize_time(payload.get("offline_evolution_time")),
        last_offline_evolution_run_date=last_run,
        strategy=_normalize_strategy_state(payload.get("strategy")),
        risk=_normalize_risk_state(payload.get("risk")),
    )


def save_control_state(path: Path, state: ControlState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(state), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def should_run_offline_evolution(state: ControlState, now: datetime) -> bool:
    if not state.offline_evolution_enabled:
        return False
    today = now.date().isoformat()
    if state.last_offline_evolution_run_date == today:
        return False

    configured = datetime.strptime(state.offline_evolution_time, "%H:%M").time()
    return now.time() >= configured
