from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class RandomFlipState:
    opened_at: str | None = None
    side: str | None = None
    quantity: float | None = None
    last_closed_at: str | None = None


@dataclass(frozen=True)
class RandomFlipPlan:
    action: str
    reason: str
    side: str | None = None


class RandomFlipStrategy:
    name = "random_flip"

    def load_state(self, path: Path) -> RandomFlipState:
        if not path.exists():
            return RandomFlipState()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return RandomFlipState()
        if not isinstance(payload, dict):
            return RandomFlipState()
        return RandomFlipState(
            opened_at=str(payload["opened_at"]) if payload.get("opened_at") else None,
            side=str(payload["side"]) if payload.get("side") else None,
            quantity=float(payload["quantity"]) if payload.get("quantity") is not None else None,
            last_closed_at=str(payload["last_closed_at"]) if payload.get("last_closed_at") else None,
        )

    def save_state(self, path: Path, state: RandomFlipState) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(state), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def build_plan(
        self,
        *,
        position_state: dict[str, object],
        strategy_state: RandomFlipState,
        now: datetime | None,
        hold_seconds: int,
        cooldown_seconds: int,
        choose_side: Callable[[], str],
    ) -> RandomFlipPlan:
        current_time = now or datetime.now(timezone.utc)
        is_open = bool(position_state.get("is_open", False))

        if is_open:
            opened_at = self._parse_iso(strategy_state.opened_at)
            if opened_at is None:
                return RandomFlipPlan(
                    action="hold",
                    reason="position open, but hold start time is unknown",
                )
            elapsed_seconds = (current_time - opened_at).total_seconds()
            if elapsed_seconds >= hold_seconds:
                return RandomFlipPlan(
                    action="close_position",
                    reason="hold window expired",
                )
            return RandomFlipPlan(
                action="hold",
                reason="hold window still active",
            )

        if cooldown_seconds > 0 and strategy_state.last_closed_at:
            last_closed_at = self._parse_iso(strategy_state.last_closed_at)
            if last_closed_at is not None:
                elapsed_since_close = (current_time - last_closed_at).total_seconds()
                if elapsed_since_close < cooldown_seconds:
                    return RandomFlipPlan(
                        action="hold",
                        reason="cooldown window still active",
                    )

        side = choose_side()
        if side not in {"open_long", "open_short"}:
            raise ValueError(f"Unsupported random side: {side}")
        return RandomFlipPlan(
            action=side,
            reason="flat position, opening random side",
            side=side,
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

    def load_state(self, path: Path) -> RandomFlipState:
        return RandomFlipState()

    def save_state(self, path: Path, state: RandomFlipState) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(state), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def build_plan(
        self,
        *,
        position_state: dict[str, object],
        strategy_state: RandomFlipState,
        now: datetime | None,
        hold_seconds: int,
        cooldown_seconds: int,
        choose_side: Callable[[], str],
    ) -> RandomFlipPlan:
        return RandomFlipPlan(
            action="hold",
            reason="manual_only strategy selected",
        )


def get_trade_strategy(mode: str):
    normalized_mode = mode.strip().lower()
    if normalized_mode == "random_flip":
        return RandomFlipStrategy()
    if normalized_mode == "manual_only":
        return ManualOnlyStrategy()
    raise ValueError(f"Unsupported trade strategy mode: {mode}")
