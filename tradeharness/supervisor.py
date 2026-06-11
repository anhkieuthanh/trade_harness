from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import is_dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from tradeharness.config.settings import load_settings
from tradeharness.control.state import (
    ControlState,
    load_control_state,
    save_control_state,
    should_run_offline_evolution,
)
from tradeharness.evolution.scheduler import main as run_scheduled_evolution
from tradeharness.runtime.failures import (
    append_failure_episode,
    append_runtime_incident,
    format_exception,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONTROL_STATE_PATH = REPO_ROOT / "var" / "control" / "state.json"
DEFAULT_RUNTIME_INCIDENT_LOG_PATH = REPO_ROOT / "var" / "runtime" / "incidents.jsonl"


def _load_dotenv_file(path: Path = REPO_ROOT / ".env") -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def resolve_control_state_path() -> Path:
    configured = os.getenv("CONTROL_STATE_PATH", "").strip()
    if not configured:
        return DEFAULT_CONTROL_STATE_PATH
    candidate = Path(configured).expanduser()
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def build_streamlit_command(*, port: int = 8501) -> list[str]:
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "streamlit_app.py",
        "--server.headless",
        "true",
        "--server.port",
        str(port),
    ]


def maybe_run_live_cycle(
    state: ControlState,
    *,
    load_settings_func: Callable[[], object] = load_settings,
    run_agent_cycle_func: Callable[[object], None] | None = None,
) -> None:
    if not state.live_enabled:
        return
    if run_agent_cycle_func is None:
        try:
            from tradeharness.runtime.agent import run_agent_cycle as run_agent_cycle_func
        except ImportError as exc:
            print(
                f"[supervisor] live loop disabled by missing dependency: {exc}",
                file=sys.stderr,
            )
            return

    settings = load_settings_func()
    if is_dataclass(settings):
        settings = replace(
            settings,
            trade_strategy_mode=state.strategy.mode,
            trade_entry_quantity_btc=state.strategy.entry_quantity_btc,
            trade_hold_seconds=state.strategy.hold_seconds,
            trade_cooldown_seconds=state.strategy.cooldown_seconds,
            trade_risk_max_daily_loss_usdt=state.risk.max_daily_loss_usdt,
            trade_risk_max_open_positions=state.risk.max_open_positions,
            trade_risk_loss_cooldown_seconds=state.risk.loss_cooldown_seconds,
            trade_risk_hard_stop_candle_range_pct=state.risk.hard_stop_candle_range_pct,
        )
    run_agent_cycle_func(settings)


def maybe_run_scheduled_evolution(
    control_state_path: Path,
    *,
    now: datetime | None = None,
    scheduler_main_func: Callable[[], None] = run_scheduled_evolution,
) -> bool:
    current_time = now or datetime.now(timezone.utc).astimezone()
    state = load_control_state(control_state_path)
    if not should_run_offline_evolution(state, current_time):
        return False

    scheduler_main_func()
    save_control_state(
        control_state_path,
        ControlState(
            live_enabled=state.live_enabled,
            offline_evolution_enabled=state.offline_evolution_enabled,
            offline_evolution_time=state.offline_evolution_time,
            last_offline_evolution_run_date=current_time.date().isoformat(),
            strategy=state.strategy,
            risk=state.risk,
        ),
    )
    return True


def _record_supervisor_failure(exc: BaseException, *, phase: str) -> None:
    error_message = format_exception(exc)
    incident_path = str(DEFAULT_RUNTIME_INCIDENT_LOG_PATH)
    try:
        settings = load_settings()
    except Exception:
        settings = None

    if settings is not None:
        incident_path = settings.runtime_incident_log_path
        try:
            append_failure_episode(
                trajectory_log_path=settings.trajectory_log_path,
                task_id=settings.task_id,
                harness_version=settings.harness_version,
                symbol=settings.symbol,
                mode="supervisor",
                phase=phase,
                error_message=error_message,
                termination_reason=f"{phase}_exception",
                final_tag="supervisor_exception",
            )
        except Exception:
            pass

    try:
        append_runtime_incident(
            incident_path,
            component="supervisor",
            phase=phase,
            message=error_message,
        )
    except Exception:
        pass
    print(f"[supervisor] {phase} error: {error_message}", file=sys.stderr)


def run_worker(control_state_path: Path, *, sleep_seconds: int = 5) -> None:
    while True:
        try:
            state = load_control_state(control_state_path)
            maybe_run_live_cycle(state)
        except Exception as exc:
            _record_supervisor_failure(exc, phase="live_cycle")

        try:
            maybe_run_scheduled_evolution(control_state_path)
        except Exception as exc:
            _record_supervisor_failure(exc, phase="offline_evolution")
        time.sleep(sleep_seconds)


def main() -> None:
    _load_dotenv_file()
    control_state_path = resolve_control_state_path()
    if not control_state_path.exists():
        save_control_state(control_state_path, ControlState())

    # Start Svelte UI server in background thread
    try:
        import threading
        from tradeharness.ui_server import run_server as run_ui_server
        ui_port = int(os.getenv("UI_PORT", "8080"))
        ui_thread = threading.Thread(target=run_ui_server, args=(ui_port,), daemon=True)
        ui_thread.start()
        print(f"[supervisor] Svelte UI server started on port {ui_port}")
    except Exception as e:
        import sys
        print(f"[supervisor] failed to start Svelte UI server: {e}", file=sys.stderr)

    streamlit_port = int(os.getenv("STREAMLIT_PORT", "8501"))
    streamlit_process = subprocess.Popen(  # noqa: S603
        build_streamlit_command(port=streamlit_port),
        cwd=REPO_ROOT,
    )
    try:
        run_worker(control_state_path)
    finally:
        streamlit_process.terminate()


if __name__ == "__main__":
    main()
