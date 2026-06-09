from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from tradeharness.control.state import (
    ControlState,
    RiskControlState,
    StrategyControlState,
    load_control_state,
    save_control_state,
    should_run_offline_evolution,
)
from tradeharness.config.settings import Settings
from tradeharness.supervisor import (
    build_streamlit_command,
    maybe_run_live_cycle,
    maybe_run_scheduled_evolution,
    resolve_control_state_path,
    _load_dotenv_file,
)


class ControlStateTests(unittest.TestCase):
    def test_load_control_state_returns_safe_defaults_when_missing(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            state = load_control_state(Path(temp_dir_name) / "state.json")

        self.assertFalse(state.live_enabled)
        self.assertTrue(state.offline_evolution_enabled)
        self.assertEqual(state.offline_evolution_time, "01:00")
        self.assertIsNone(state.last_offline_evolution_run_date)

    def test_save_control_state_creates_parent_directory_and_round_trips(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            path = Path(temp_dir_name) / "var" / "control" / "state.json"
            state = ControlState(
                live_enabled=True,
                offline_evolution_enabled=False,
                offline_evolution_time="23:30",
                last_offline_evolution_run_date="2026-06-09",
            )

            save_control_state(path, state)
            loaded = load_control_state(path)

        self.assertEqual(loaded, state)

    def test_load_control_state_normalizes_invalid_time_to_default(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            path = Path(temp_dir_name) / "state.json"
            path.write_text(
                json.dumps({"offline_evolution_time": "bad-time"}),
                encoding="utf-8",
            )

            state = load_control_state(path)

        self.assertEqual(state.offline_evolution_time, "01:00")

    def test_should_run_offline_evolution_after_configured_time_once_per_day(self) -> None:
        state = ControlState(
            offline_evolution_enabled=True,
            offline_evolution_time="01:00",
            last_offline_evolution_run_date=None,
        )
        now = datetime(2026, 6, 9, 1, 5, tzinfo=timezone.utc)

        self.assertTrue(should_run_offline_evolution(state, now))

        already_ran = ControlState(
            offline_evolution_enabled=True,
            offline_evolution_time="01:00",
            last_offline_evolution_run_date="2026-06-09",
        )
        self.assertFalse(should_run_offline_evolution(already_ran, now))

    def test_should_not_run_offline_evolution_before_time_or_when_disabled(self) -> None:
        before_time = datetime(2026, 6, 9, 0, 59, tzinfo=timezone.utc)
        enabled = ControlState(
            offline_evolution_enabled=True,
            offline_evolution_time="01:00",
        )
        disabled = ControlState(
            offline_evolution_enabled=False,
            offline_evolution_time="01:00",
        )

        self.assertFalse(should_run_offline_evolution(enabled, before_time))
        self.assertFalse(should_run_offline_evolution(disabled, before_time))


class SupervisorTests(unittest.TestCase):
    def test_build_streamlit_command_points_to_local_dashboard(self) -> None:
        command = build_streamlit_command(port=8502)

        self.assertEqual(command[1:5], ["-m", "streamlit", "run", "streamlit_app.py"])
        self.assertIn("--server.headless", command)
        self.assertIn("true", command)
        self.assertIn("--server.port", command)
        self.assertIn("8502", command)

    def test_resolve_control_state_path_uses_dotenv_value_when_loaded(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            env_path = temp_dir / ".env"
            env_path.write_text("CONTROL_STATE_PATH=custom/control.json\n", encoding="utf-8")

            with patch.dict("os.environ", {}, clear=True):
                _load_dotenv_file(env_path)
                path = resolve_control_state_path()

        self.assertEqual(path.name, "control.json")
        self.assertIn("custom", str(path))

    def test_maybe_run_live_cycle_skips_when_live_disabled(self) -> None:
        run_agent_cycle = Mock()
        load_settings = Mock()

        maybe_run_live_cycle(
            ControlState(live_enabled=False),
            load_settings_func=load_settings,
            run_agent_cycle_func=run_agent_cycle,
        )

        load_settings.assert_not_called()
        run_agent_cycle.assert_not_called()

    def test_maybe_run_live_cycle_runs_when_live_enabled(self) -> None:
        settings = Mock()
        run_agent_cycle = Mock()
        load_settings = Mock(return_value=settings)

        maybe_run_live_cycle(
            ControlState(live_enabled=True),
            load_settings_func=load_settings,
            run_agent_cycle_func=run_agent_cycle,
        )

        load_settings.assert_called_once_with()
        run_agent_cycle.assert_called_once_with(settings)

    def test_maybe_run_live_cycle_applies_strategy_overrides(self) -> None:
        settings = Settings(
            binance_api_key="key",
            binance_api_secret="secret",
            lmstudio_base_url="http://localhost:1234/v1",
            lmstudio_model="google/gemma-4-e2b",
            symbol="BTCUSDT",
            poll_interval_seconds=30,
            candle_interval="1m",
            candle_limit=5,
            trade_size_percent=10.0,
            trade_strategy_mode="random_flip",
            trade_entry_quantity_btc=0.008,
            trade_hold_seconds=120,
            trade_cooldown_seconds=0,
            trade_strategy_state_path="var/control/trade_strategy_state.json",
            trade_risk_max_daily_loss_usdt=50.0,
            trade_risk_max_open_positions=1,
            trade_risk_loss_cooldown_seconds=1800,
            trade_risk_hard_stop_candle_range_pct=2.0,
            trade_risk_state_path="var/control/risk_state.json",
            dry_run=True,
            evaluator_base_url="http://localhost:1234/v1",
            evaluator_api_key="",
            evaluator_model="gpt-5.4",
            trajectory_log_path="var/trajectories/episodes.jsonl",
            evolution_output_dir="var/evolution",
            evolution_runs_dir="var/evolution/runs",
            evolution_minimum_support=1,
            active_contract_artifact_path="tradeharness/evolution/artifacts/current/contract.json",
            active_skills_artifact_path="tradeharness/evolution/artifacts/current/skills.json",
            active_action_rules_artifact_path="tradeharness/evolution/artifacts/current/action_rules.json",
            active_trajectory_rules_artifact_path="tradeharness/evolution/artifacts/current/trajectory_rules.json",
            active_harness_meta_artifact_path="tradeharness/evolution/artifacts/current/harness_meta.json",
            harness_version="local",
            task_id="trade:BTCUSDT:1m:5:inspect_then_decide",
        )
        run_agent_cycle = Mock()
        load_settings = Mock(return_value=settings)

        maybe_run_live_cycle(
            ControlState(
                live_enabled=True,
                strategy=StrategyControlState(
                    mode="manual_only",
                    entry_quantity_btc=0.01,
                    hold_seconds=300,
                    cooldown_seconds=45,
                ),
                risk=RiskControlState(
                    max_daily_loss_usdt=25.0,
                    max_open_positions=1,
                    loss_cooldown_seconds=900,
                    hard_stop_candle_range_pct=1.5,
                ),
            ),
            load_settings_func=load_settings,
            run_agent_cycle_func=run_agent_cycle,
        )

        run_agent_cycle.assert_called_once()
        called_settings = run_agent_cycle.call_args.args[0]
        self.assertEqual(called_settings.trade_strategy_mode, "manual_only")
        self.assertEqual(called_settings.trade_entry_quantity_btc, 0.01)
        self.assertEqual(called_settings.trade_hold_seconds, 300)
        self.assertEqual(called_settings.trade_cooldown_seconds, 45)
        self.assertEqual(called_settings.trade_risk_max_daily_loss_usdt, 25.0)
        self.assertEqual(called_settings.trade_risk_max_open_positions, 1)
        self.assertEqual(called_settings.trade_risk_loss_cooldown_seconds, 900)
        self.assertEqual(called_settings.trade_risk_hard_stop_candle_range_pct, 1.5)

    def test_maybe_run_live_cycle_gracefully_skips_missing_runtime_dependency(self) -> None:
        original_import = __import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "tradeharness.runtime.agent":
                raise ImportError("No module named 'requests'")
            return original_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=fake_import), patch("tradeharness.supervisor.sys.stderr"):
            maybe_run_live_cycle(
                ControlState(live_enabled=True),
                load_settings_func=Mock(return_value=Mock()),
                run_agent_cycle_func=None,
            )

    def test_maybe_run_scheduled_evolution_runs_once_and_persists_date(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            path = Path(temp_dir_name) / "state.json"
            save_control_state(
                path,
                ControlState(
                    offline_evolution_enabled=True,
                    offline_evolution_time="01:00",
                ),
            )
            scheduler_main = Mock()
            now = datetime(2026, 6, 9, 1, 5, tzinfo=timezone.utc)

            did_run = maybe_run_scheduled_evolution(
                path,
                now=now,
                scheduler_main_func=scheduler_main,
            )
            loaded = load_control_state(path)

        self.assertTrue(did_run)
        scheduler_main.assert_called_once_with()
        self.assertEqual(loaded.last_offline_evolution_run_date, "2026-06-09")

    def test_maybe_run_scheduled_evolution_skips_before_time(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            path = Path(temp_dir_name) / "state.json"
            save_control_state(
                path,
                ControlState(
                    offline_evolution_enabled=True,
                    offline_evolution_time="01:00",
                ),
            )
            scheduler_main = Mock()
            now = datetime(2026, 6, 9, 0, 30, tzinfo=timezone.utc)

            did_run = maybe_run_scheduled_evolution(
                path,
                now=now,
                scheduler_main_func=scheduler_main,
            )

        self.assertFalse(did_run)
        scheduler_main.assert_not_called()


if __name__ == "__main__":
    unittest.main()
