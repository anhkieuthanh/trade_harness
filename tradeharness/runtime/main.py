from __future__ import annotations

import time

from tradeharness.config.settings import load_settings
from tradeharness.runtime.agent import run_agent_cycle


def run_once() -> None:
    settings = load_settings()
    run_agent_cycle(settings)


def main() -> None:
    settings = load_settings()
    while True:
        run_once()
        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    main()
