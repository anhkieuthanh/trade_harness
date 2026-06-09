from __future__ import annotations

import time

from tradeharness.config.settings import load_settings
from tradeharness.runtime.failures import append_failure_episode, append_runtime_incident, format_exception
from tradeharness.runtime.agent import run_agent_cycle


def run_once() -> None:
    settings = load_settings()
    run_agent_cycle(settings)


def main() -> None:
    settings = load_settings()
    while True:
        try:
            run_once()
        except Exception as exc:
            error_message = format_exception(exc)
            try:
                append_failure_episode(
                    trajectory_log_path=settings.trajectory_log_path,
                    task_id=settings.task_id,
                    harness_version=settings.harness_version,
                    symbol=settings.symbol,
                    mode="runtime_main",
                    phase="runtime_main",
                    error_message=error_message,
                    termination_reason="runtime_main_exception",
                    final_tag="runtime_main_exception",
                )
            except Exception:
                pass
            try:
                append_runtime_incident(
                    settings.runtime_incident_log_path,
                    component="runtime_main",
                    phase="run_once",
                    message=error_message,
                )
            except Exception:
                pass
        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    main()
