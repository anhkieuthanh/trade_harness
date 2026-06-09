# One Command System Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one command that starts the full TradeHarness local system: runtime agent loop, Streamlit operator monitor, and daily offline evolution scheduler.

**Architecture:** Add a small Python supervisor under `tradeharness/system/` instead of shell scripts. The supervisor builds deterministic process specs, starts each component as a child process, streams logs into `var/system/`, and shuts everything down cleanly on `Ctrl+C`. The existing runtime, Streamlit app, and evolution scheduler remain independent modules.

**Tech Stack:** Python standard library (`argparse`, `subprocess`, `signal`, `threading`, `time`, `dataclasses`, `pathlib`), existing TradeHarness modules, Streamlit CLI.

---

## File Structure

- Create `tradeharness/system/__init__.py`: package marker and public exports.
- Create `tradeharness/system/processes.py`: process spec dataclass and command builders for runtime, monitor, and evolution loop.
- Create `tradeharness/system/evolution_loop.py`: long-running daily scheduler wrapper around `tradeharness.evolution.scheduler`.
- Create `tradeharness/system/supervisor.py`: process lifecycle manager, log file wiring, shutdown handling.
- Create `tradeharness/system/main.py`: CLI entrypoint for `python3 -m tradeharness.system`.
- Create `tradeharness/system/__main__.py`: module execution shim.
- Create `tests/test_system_runner.py`: focused unit tests for command building and supervisor behavior with fake process factory.
- Modify `README.MD`: document the one-command run path.
- Modify `.env.example`: add optional system runner settings.

---

### Task 1: Process Specs and Command Builders

**Files:**
- Create: `tradeharness/system/__init__.py`
- Create: `tradeharness/system/processes.py`
- Test: `tests/test_system_runner.py`

- [ ] **Step 1: Write failing tests for process specs**

Add this to `tests/test_system_runner.py`:

```python
from __future__ import annotations

import sys
import unittest
from pathlib import Path

from tradeharness.system.processes import (
    SystemRunnerConfig,
    build_evolution_spec,
    build_monitor_spec,
    build_runtime_spec,
    build_system_process_specs,
)


class SystemRunnerProcessSpecTests(unittest.TestCase):
    def test_build_runtime_spec_points_to_tradeharness_main(self) -> None:
        spec = build_runtime_spec()

        self.assertEqual(spec.name, "runtime")
        self.assertEqual(spec.command, [sys.executable, "-m", "tradeharness.main"])

    def test_build_monitor_spec_uses_streamlit_cli_and_port(self) -> None:
        spec = build_monitor_spec(port=8502, address="127.0.0.1")

        self.assertEqual(spec.name, "monitor")
        self.assertEqual(
            spec.command,
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "streamlit_app.py",
                "--server.port",
                "8502",
                "--server.address",
                "127.0.0.1",
            ],
        )

    def test_build_evolution_spec_points_to_system_evolution_loop(self) -> None:
        spec = build_evolution_spec(interval_seconds=86400, run_on_start=False)

        self.assertEqual(spec.name, "evolution")
        self.assertEqual(
            spec.command,
            [
                sys.executable,
                "-m",
                "tradeharness.system.evolution_loop",
                "--interval-seconds",
                "86400",
            ],
        )

    def test_build_system_process_specs_includes_all_components_by_default(self) -> None:
        config = SystemRunnerConfig(repo_root=Path("/repo"))

        specs = build_system_process_specs(config)

        self.assertEqual([spec.name for spec in specs], ["runtime", "monitor", "evolution"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_system_runner -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'tradeharness.system'`.

- [ ] **Step 3: Add process spec implementation**

Create `tradeharness/system/__init__.py`:

```python
from __future__ import annotations

from tradeharness.system.processes import ProcessSpec, SystemRunnerConfig

__all__ = ["ProcessSpec", "SystemRunnerConfig"]
```

Create `tradeharness/system/processes.py`:

```python
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProcessSpec:
    name: str
    command: list[str]
    log_name: str


@dataclass(frozen=True)
class SystemRunnerConfig:
    repo_root: Path
    include_runtime: bool = True
    include_monitor: bool = True
    include_evolution: bool = True
    monitor_port: int = 8501
    monitor_address: str = "127.0.0.1"
    evolution_interval_seconds: int = 86400
    evolution_run_on_start: bool = False


def build_runtime_spec() -> ProcessSpec:
    return ProcessSpec(
        name="runtime",
        command=[sys.executable, "-m", "tradeharness.main"],
        log_name="runtime.log",
    )


def build_monitor_spec(*, port: int, address: str) -> ProcessSpec:
    return ProcessSpec(
        name="monitor",
        command=[
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "streamlit_app.py",
            "--server.port",
            str(port),
            "--server.address",
            address,
        ],
        log_name="monitor.log",
    )


def build_evolution_spec(
    *,
    interval_seconds: int,
    run_on_start: bool,
) -> ProcessSpec:
    command = [
        sys.executable,
        "-m",
        "tradeharness.system.evolution_loop",
        "--interval-seconds",
        str(interval_seconds),
    ]
    if run_on_start:
        command.append("--run-on-start")
    return ProcessSpec(
        name="evolution",
        command=command,
        log_name="evolution.log",
    )


def build_system_process_specs(config: SystemRunnerConfig) -> list[ProcessSpec]:
    specs: list[ProcessSpec] = []
    if config.include_runtime:
        specs.append(build_runtime_spec())
    if config.include_monitor:
        specs.append(
            build_monitor_spec(
                port=config.monitor_port,
                address=config.monitor_address,
            )
        )
    if config.include_evolution:
        specs.append(
            build_evolution_spec(
                interval_seconds=config.evolution_interval_seconds,
                run_on_start=config.evolution_run_on_start,
            )
        )
    return specs
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_system_runner -v
```

Expected: PASS.

- [ ] **Step 5: Commit process spec task**

```bash
git add tradeharness/system/__init__.py tradeharness/system/processes.py tests/test_system_runner.py
git commit -m "feat: add system runner process specs"
```

---

### Task 2: Evolution Loop Process

**Files:**
- Create: `tradeharness/system/evolution_loop.py`
- Test: `tests/test_system_runner.py`

- [ ] **Step 1: Write failing tests for evolution loop timing decisions**

Append this test class to `tests/test_system_runner.py`:

```python
from tradeharness.system.evolution_loop import should_run_now


class EvolutionLoopTests(unittest.TestCase):
    def test_should_run_now_is_true_when_never_run(self) -> None:
        self.assertTrue(should_run_now(last_run_epoch=None, now_epoch=100.0, interval_seconds=60))

    def test_should_run_now_waits_until_interval_elapses(self) -> None:
        self.assertFalse(should_run_now(last_run_epoch=100.0, now_epoch=120.0, interval_seconds=60))
        self.assertTrue(should_run_now(last_run_epoch=100.0, now_epoch=160.0, interval_seconds=60))
```

- [ ] **Step 2: Run targeted tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_system_runner -v
```

Expected: FAIL with `ModuleNotFoundError` or missing `should_run_now`.

- [ ] **Step 3: Implement the evolution loop**

Create `tradeharness/system/evolution_loop.py`:

```python
from __future__ import annotations

import argparse
import time

from tradeharness.evolution.scheduler import main as run_scheduler_once


def should_run_now(
    *,
    last_run_epoch: float | None,
    now_epoch: float,
    interval_seconds: int,
) -> bool:
    if last_run_epoch is None:
        return True
    return now_epoch - last_run_epoch >= interval_seconds


def run_loop(
    *,
    interval_seconds: int,
    run_on_start: bool,
    sleep_seconds: int = 30,
) -> None:
    last_run_epoch = None if run_on_start else time.time()
    while True:
        now_epoch = time.time()
        if should_run_now(
            last_run_epoch=last_run_epoch,
            now_epoch=now_epoch,
            interval_seconds=interval_seconds,
        ):
            run_scheduler_once()
            last_run_epoch = time.time()
        time.sleep(sleep_seconds)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TradeHarness offline evolution on an interval.")
    parser.add_argument("--interval-seconds", type=int, default=86400)
    parser.add_argument("--run-on-start", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    run_loop(
        interval_seconds=args.interval_seconds,
        run_on_start=args.run_on_start,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run targeted tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_system_runner -v
```

Expected: PASS.

- [ ] **Step 5: Commit evolution loop task**

```bash
git add tradeharness/system/evolution_loop.py tests/test_system_runner.py
git commit -m "feat: add system evolution loop"
```

---

### Task 3: Supervisor Lifecycle

**Files:**
- Create: `tradeharness/system/supervisor.py`
- Test: `tests/test_system_runner.py`

- [ ] **Step 1: Write failing tests for supervisor start and stop**

Append this to `tests/test_system_runner.py`:

```python
from tradeharness.system.processes import ProcessSpec
from tradeharness.system.supervisor import SystemSupervisor


class FakeProcess:
    def __init__(self) -> None:
        self.terminated = False
        self.killed = False
        self.wait_calls = 0
        self.returncode = None

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


class SystemSupervisorTests(unittest.TestCase):
    def test_supervisor_starts_each_process_spec(self) -> None:
        created_commands: list[list[str]] = []

        def fake_factory(command, **kwargs):
            created_commands.append(command)
            return FakeProcess()

        specs = [
            ProcessSpec(name="runtime", command=["python3", "-m", "tradeharness.main"], log_name="runtime.log"),
            ProcessSpec(name="monitor", command=["python3", "-m", "streamlit"], log_name="monitor.log"),
        ]
        supervisor = SystemSupervisor(
            repo_root=Path("/repo"),
            specs=specs,
            process_factory=fake_factory,
        )

        supervisor.start()

        self.assertEqual(created_commands, [spec.command for spec in specs])

    def test_supervisor_stop_terminates_children(self) -> None:
        processes: list[FakeProcess] = []

        def fake_factory(command, **kwargs):
            process = FakeProcess()
            processes.append(process)
            return process

        supervisor = SystemSupervisor(
            repo_root=Path("/repo"),
            specs=[ProcessSpec(name="runtime", command=["python3"], log_name="runtime.log")],
            process_factory=fake_factory,
        )

        supervisor.start()
        supervisor.stop()

        self.assertTrue(processes[0].terminated)
        self.assertEqual(processes[0].wait_calls, 1)
```

- [ ] **Step 2: Run targeted tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_system_runner -v
```

Expected: FAIL because `tradeharness.system.supervisor` does not exist.

- [ ] **Step 3: Implement supervisor**

Create `tradeharness/system/supervisor.py`:

```python
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from tradeharness.system.processes import ProcessSpec


class ManagedProcess(Protocol):
    returncode: int | None

    def poll(self) -> int | None: ...
    def terminate(self) -> None: ...
    def kill(self) -> None: ...
    def wait(self, timeout: float | None = None) -> int: ...


ProcessFactory = Callable[..., ManagedProcess]


@dataclass
class RunningProcess:
    spec: ProcessSpec
    process: ManagedProcess


class SystemSupervisor:
    def __init__(
        self,
        *,
        repo_root: Path,
        specs: list[ProcessSpec],
        process_factory: ProcessFactory = subprocess.Popen,
        log_dir: Path | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.specs = specs
        self.process_factory = process_factory
        self.log_dir = log_dir or repo_root / "var" / "system"
        self.running: list[RunningProcess] = []
        self._log_handles = []

    def start(self) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        for spec in self.specs:
            log_path = self.log_dir / spec.log_name
            log_handle = log_path.open("a", encoding="utf-8")
            self._log_handles.append(log_handle)
            process = self.process_factory(
                spec.command,
                cwd=self.repo_root,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
            )
            self.running.append(RunningProcess(spec=spec, process=process))

    def stop(self, *, timeout_seconds: float = 10.0) -> None:
        for item in self.running:
            if item.process.poll() is None:
                item.process.terminate()
        for item in self.running:
            try:
                item.process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                item.process.kill()
                item.process.wait(timeout=timeout_seconds)
        for handle in self._log_handles:
            handle.close()
        self._log_handles.clear()

    def wait_forever(self, *, poll_seconds: float = 2.0) -> None:
        while True:
            for item in self.running:
                returncode = item.process.poll()
                if returncode is not None:
                    raise RuntimeError(f"{item.spec.name} exited unexpectedly with code {returncode}")
            time.sleep(poll_seconds)
```

- [ ] **Step 4: Run targeted tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_system_runner -v
```

Expected: PASS.

- [ ] **Step 5: Commit supervisor task**

```bash
git add tradeharness/system/supervisor.py tests/test_system_runner.py
git commit -m "feat: add system process supervisor"
```

---

### Task 4: CLI Entrypoint

**Files:**
- Create: `tradeharness/system/main.py`
- Create: `tradeharness/system/__main__.py`
- Modify: `tradeharness/system/__init__.py`
- Test: `tests/test_system_runner.py`

- [ ] **Step 1: Write failing tests for CLI config parsing**

Append this to `tests/test_system_runner.py`:

```python
from tradeharness.system.main import build_config_from_args, parse_args


class SystemRunnerCliTests(unittest.TestCase):
    def test_parse_args_defaults_to_all_components(self) -> None:
        args = parse_args([])

        self.assertFalse(args.no_runtime)
        self.assertFalse(args.no_monitor)
        self.assertFalse(args.no_evolution)
        self.assertEqual(args.monitor_port, 8501)

    def test_build_config_from_args_disables_monitor(self) -> None:
        args = parse_args(["--no-monitor", "--monitor-port", "8503"])

        config = build_config_from_args(args, repo_root=Path("/repo"))

        self.assertTrue(config.include_runtime)
        self.assertFalse(config.include_monitor)
        self.assertTrue(config.include_evolution)
        self.assertEqual(config.monitor_port, 8503)
```

- [ ] **Step 2: Run targeted tests to verify they fail**

Run:

```bash
python3 -m unittest tests.test_system_runner -v
```

Expected: FAIL because CLI module does not exist.

- [ ] **Step 3: Implement CLI**

Create `tradeharness/system/main.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path

from tradeharness.system.processes import SystemRunnerConfig, build_system_process_specs
from tradeharness.system.supervisor import SystemSupervisor

REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full TradeHarness local system.")
    parser.add_argument("--no-runtime", action="store_true")
    parser.add_argument("--no-monitor", action="store_true")
    parser.add_argument("--no-evolution", action="store_true")
    parser.add_argument("--monitor-port", type=int, default=8501)
    parser.add_argument("--monitor-address", default="127.0.0.1")
    parser.add_argument("--evolution-interval-seconds", type=int, default=86400)
    parser.add_argument("--evolution-run-on-start", action="store_true")
    return parser.parse_args(argv)


def build_config_from_args(
    args: argparse.Namespace,
    *,
    repo_root: Path,
) -> SystemRunnerConfig:
    return SystemRunnerConfig(
        repo_root=repo_root,
        include_runtime=not args.no_runtime,
        include_monitor=not args.no_monitor,
        include_evolution=not args.no_evolution,
        monitor_port=args.monitor_port,
        monitor_address=args.monitor_address,
        evolution_interval_seconds=args.evolution_interval_seconds,
        evolution_run_on_start=args.evolution_run_on_start,
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    config = build_config_from_args(args, repo_root=REPO_ROOT)
    specs = build_system_process_specs(config)
    supervisor = SystemSupervisor(repo_root=config.repo_root, specs=specs)
    try:
        supervisor.start()
        print("TradeHarness system started.")
        print(f"Streamlit monitor: http://{config.monitor_address}:{config.monitor_port}")
        print("Logs: var/system/")
        supervisor.wait_forever()
    except KeyboardInterrupt:
        print("Stopping TradeHarness system...")
    finally:
        supervisor.stop()


if __name__ == "__main__":
    main()
```

Create `tradeharness/system/__main__.py`:

```python
from __future__ import annotations

from tradeharness.system.main import main


if __name__ == "__main__":
    main()
```

Update `tradeharness/system/__init__.py`:

```python
from __future__ import annotations

from tradeharness.system.processes import ProcessSpec, SystemRunnerConfig
from tradeharness.system.supervisor import SystemSupervisor

__all__ = ["ProcessSpec", "SystemRunnerConfig", "SystemSupervisor"]
```

- [ ] **Step 4: Run targeted tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_system_runner -v
```

Expected: PASS.

- [ ] **Step 5: Verify module help command**

Run:

```bash
python3 -m tradeharness.system --help
```

Expected: exits `0` and prints options including `--no-runtime`, `--no-monitor`, and `--no-evolution`.

- [ ] **Step 6: Commit CLI task**

```bash
git add tradeharness/system/main.py tradeharness/system/__main__.py tradeharness/system/__init__.py tests/test_system_runner.py
git commit -m "feat: add one-command system cli"
```

---

### Task 5: Environment Defaults and Documentation

**Files:**
- Modify: `.env.example`
- Modify: `README.MD`
- Test: `tests/test_system_runner.py`

- [ ] **Step 1: Add optional system runner env notes**

Update `.env.example` by adding this block near runtime settings:

```dotenv
# One-command system runner
SYSTEM_MONITOR_PORT=8501
SYSTEM_MONITOR_ADDRESS=127.0.0.1
SYSTEM_EVOLUTION_INTERVAL_SECONDS=86400
SYSTEM_EVOLUTION_RUN_ON_START=false
```

- [ ] **Step 2: Update CLI to use env defaults**

Modify `tradeharness/system/main.py` so `parse_args()` uses environment-backed defaults:

```python
import os


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
```

Then set these defaults inside `parse_args()`:

```python
parser.add_argument("--monitor-port", type=int, default=int(os.getenv("SYSTEM_MONITOR_PORT", "8501")))
parser.add_argument("--monitor-address", default=os.getenv("SYSTEM_MONITOR_ADDRESS", "127.0.0.1"))
parser.add_argument(
    "--evolution-interval-seconds",
    type=int,
    default=int(os.getenv("SYSTEM_EVOLUTION_INTERVAL_SECONDS", "86400")),
)
parser.add_argument(
    "--evolution-run-on-start",
    action="store_true",
    default=_env_bool("SYSTEM_EVOLUTION_RUN_ON_START", False),
)
```

- [ ] **Step 3: Add README one-command section**

Add this to `README.MD` under `## Run`:

```md
Full local system:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m tradeharness.system
```

This starts:

- the live agent runtime loop
- the Streamlit operator monitor at `http://127.0.0.1:8501`
- the offline evolution scheduler loop

Child process logs are written to:

- `var/system/runtime.log`
- `var/system/monitor.log`
- `var/system/evolution.log`

Stop the full system with `Ctrl+C`.
```

- [ ] **Step 4: Run targeted tests**

Run:

```bash
python3 -m unittest tests.test_system_runner -v
```

Expected: PASS.

- [ ] **Step 5: Run help command**

Run:

```bash
python3 -m tradeharness.system --help
```

Expected: exits `0`.

- [ ] **Step 6: Commit docs and env task**

```bash
git add .env.example README.MD tradeharness/system/main.py tests/test_system_runner.py
git commit -m "docs: document one-command system runner"
```

---

### Task 6: Final Verification

**Files:**
- No new files unless verification exposes a bug.

- [ ] **Step 1: Run system runner tests**

Run:

```bash
python3 -m unittest tests.test_system_runner -v
```

Expected: PASS.

- [ ] **Step 2: Run existing dashboard tests**

Run:

```bash
python3 -m unittest tests.test_streamlit_dashboard -v
```

Expected: PASS.

- [ ] **Step 3: Run existing runtime/evolution tests**

Run:

```bash
python3 -m unittest tests.test_agent_tools tests.test_offline_evolution -v
```

Expected: PASS.

- [ ] **Step 4: Compile check**

Run:

```bash
python3 -m compileall tradeharness tests streamlit_app.py
```

Expected: completes without syntax errors.

- [ ] **Step 5: Smoke-test help entrypoint only**

Run:

```bash
python3 -m tradeharness.system --help
```

Expected: exits `0`.

- [ ] **Step 6: Do not start live trading during automated verification**

Do not run `python3 -m tradeharness.system` as an automated test because it starts long-running processes and may connect to LM Studio/Binance depending on `.env`.

