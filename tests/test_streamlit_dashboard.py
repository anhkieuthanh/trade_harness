from __future__ import annotations

import unittest
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from tradeharness.evolution.metrics import compute_pass_at_1
from streamlit_app import (
    DashboardState,
    build_offline_evolution_command,
    build_header_context,
    build_evolution_summary_rows,
    bump_refresh_nonce,
    compute_recent_pass_at_1,
    get_refresh_nonce,
    load_env_settings,
    load_harness_meta,
    load_latest_evolution_snapshot,
    main,
    render_control_panel,
    render_control_fragment,
    render_critical_status_strip,
    render_evolution_fragment,
    render_runtime_fragment,
    render_safe_ops,
    render_header,
    resolve_dashboard_paths,
    run_safe_command,
    summarize_latest_steps,
)
from tradeharness.control.state import (
    ControlState,
    RiskControlState,
    StrategyControlState,
    load_control_state,
)


class StreamlitDashboardLoaderTests(unittest.TestCase):
    def test_load_env_settings_reads_key_values(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            env_path = temp_dir / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "# comment",
                        "HARNESS_VERSION=v4",
                        "TASK_ID=trade:BTCUSDT:1m:5:inspect_then_decide",
                    ]
                ),
                encoding="utf-8",
            )

            payload = load_env_settings(str(env_path))

            self.assertEqual(payload["HARNESS_VERSION"], "v4")
            self.assertEqual(
                payload["TASK_ID"],
                "trade:BTCUSDT:1m:5:inspect_then_decide",
            )

    def test_load_harness_meta_prefers_artifact_values(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            meta_path = temp_dir / "harness_meta.json"
            meta_path.write_text('{"harness_version":"v3"}', encoding="utf-8")

            payload = load_harness_meta(meta_path)

            self.assertEqual(payload["harness_version"], "v3")

    def test_load_latest_evolution_snapshot_handles_missing_files(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)

            snapshot = load_latest_evolution_snapshot(temp_dir)

            self.assertEqual(snapshot.daily_report_text, "")
            self.assertEqual(snapshot.pass_metrics, {})
            self.assertEqual(snapshot.annotations_count, 0)

    def test_load_latest_evolution_snapshot_reads_explicit_harness_meta(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            meta_path = temp_dir / "alternate-artifacts" / "custom_meta.json"
            meta_path.parent.mkdir()
            meta_path.write_text('{"harness_version":"snapshot-v1"}', encoding="utf-8")

            snapshot = load_latest_evolution_snapshot(
                temp_dir,
                harness_meta_path=meta_path,
            )

            self.assertEqual(snapshot.harness_meta["harness_version"], "snapshot-v1")

    def test_resolve_dashboard_paths_uses_selected_log_context(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            repo_root = Path(temp_dir_name)
            log_path = repo_root / "var" / "trajectories" / "episodes.jsonl"
            log_path.parent.mkdir(parents=True)
            log_path.write_text("", encoding="utf-8")
            env_path = repo_root / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "TASK_ID=task-from-selected-log",
                        "EVOLUTION_OUTPUT_DIR=alt/evolution",
                        "ACTIVE_HARNESS_META_ARTIFACT_PATH=alt/meta/harness_meta.json",
                        "CONTROL_STATE_PATH=alt/control/state.json",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            evolution_dir = repo_root / "alt" / "evolution"
            evolution_dir.mkdir(parents=True)
            harness_meta_path = repo_root / "alt" / "meta" / "harness_meta.json"
            harness_meta_path.parent.mkdir(parents=True)
            harness_meta_path.write_text(
                '{"harness_version":"selected-harness"}',
                encoding="utf-8",
            )

            context = resolve_dashboard_paths(log_path)

            self.assertEqual(context["env_path"], env_path)
            self.assertEqual(context["evolution_dir"], evolution_dir)
            self.assertEqual(context["harness_meta_path"], harness_meta_path)
            self.assertEqual(context["control_state_path"], repo_root / "alt" / "control" / "state.json")

    def test_compute_recent_pass_at_1_matches_shared_metric_helper(self) -> None:
        episodes = [
            {"final_status": "FAILED"},
            {"final_status": "SUCCESS"},
            {"final_status": "ERROR"},
            {"final_status": "SUCCESS"},
        ]

        value = compute_recent_pass_at_1(episodes, window=3)
        expected = compute_pass_at_1(episodes[-3:])["pass_at_1"]

        self.assertEqual(value, expected)

    def test_build_header_context_uses_harness_meta_version(self) -> None:
        context = build_header_context(
            env_settings={"TASK_ID": "task-a"},
            harness_meta={"harness_version": "v9"},
        )

        self.assertEqual(context["harness_version"], "v9")
        self.assertEqual(context["task_id"], "task-a")

    def test_render_header_shows_header_context_and_manual_refresh(self) -> None:
        state = DashboardState(
            log_path=Path("/tmp/episodes.jsonl"),
            episodes=[],
            symbol="BTCUSDT",
            mode="dry_run",
            poll_interval_seconds=15,
            latest_ended_at=None,
            age_seconds=None,
            is_alive=True,
            stale_after_seconds=90,
            latest=None,
            recent_status_counts={},
            recent_decision_counts={},
        )
        header_context = {
            "harness_version": "v9",
            "task_id": "task-a",
        }
        with (
            patch("streamlit_app.st.title") as mock_title,
            patch("streamlit_app.st.caption") as mock_caption,
            patch("streamlit_app.st.button", return_value=False) as mock_button,
            patch("streamlit_app.st.rerun") as mock_rerun,
        ):
            render_header(state, header_context)

        mock_title.assert_called_once_with("TradeHarness Operator Console")
        self.assertEqual(
            mock_caption.call_args_list,
            [
                unittest.mock.call(
                    "Live runtime status, controls, and offline evolution in one operator-first view."
                ),
                unittest.mock.call("Last updated: —"),
                unittest.mock.call(
                    "Harness version: v9 · Task: task-a · Recent Pass@1: 0%"
                ),
            ],
        )
        mock_button.assert_called_once_with("Refresh now", use_container_width=True)
        mock_rerun.assert_not_called()

    def test_render_critical_status_strip_shows_six_metrics(self) -> None:
        latest = type(
            "Latest",
            (),
            {"latest_result": "SUCCESS", "harness_decision": "EXECUTE"},
        )()
        state = DashboardState(
            log_path=Path("/tmp/episodes.jsonl"),
            episodes=[],
            symbol="BTCUSDT",
            mode="dry_run",
            poll_interval_seconds=15,
            latest_ended_at=None,
            age_seconds=45,
            is_alive=True,
            stale_after_seconds=90,
            latest=latest,
            recent_status_counts={},
            recent_decision_counts={},
        )
        columns = [Mock() for _ in range(6)]
        for column in columns:
            column.metric = Mock()

        with patch("streamlit_app.st.columns", return_value=columns):
            render_critical_status_strip(state)

        columns[0].metric.assert_called_once_with("Runtime", "ALIVE")
        columns[1].metric.assert_called_once_with("Age", "0:00:45")
        columns[2].metric.assert_called_once_with("Symbol", "BTCUSDT")
        columns[3].metric.assert_called_once_with("Mode", "dry_run")
        columns[4].metric.assert_called_once_with("Latest result", "SUCCESS")
        columns[5].metric.assert_called_once_with("Harness decision", "EXECUTE")

    def test_summarize_latest_steps_returns_compact_rows(self) -> None:
        rows = summarize_latest_steps(
            {
                "steps": [
                    {
                        "step_index": 1,
                        "action": {"tool": "get_balance"},
                        "harness_intervention": {"decision": "EXECUTE"},
                        "environment_feedback": {"asset": "USDT"},
                    }
                ]
            }
        )

        self.assertEqual(rows[0]["step_index"], 1)
        self.assertEqual(rows[0]["action"], "get_balance")
        self.assertEqual(rows[0]["decision"], "EXECUTE")
        self.assertEqual(rows[0]["feedback"], '{"asset": "USDT"}')

    def test_summarize_latest_steps_distinguishes_final_response_from_missing_tool(self) -> None:
        rows = summarize_latest_steps(
            {
                "steps": [
                    {
                        "step_index": 1,
                        "action": {"final_response": "Done"},
                        "harness_intervention": {"decision": "ALLOW"},
                    },
                    {
                        "step_index": 2,
                        "action": {},
                        "harness_intervention": {"decision": "BLOCK"},
                    },
                    {
                        "step_index": 3,
                        "action": "bad-shape",
                    },
                ]
            }
        )

        self.assertEqual(rows[0]["action"], "final_response")
        self.assertEqual(rows[1]["action"], "unknown_action")
        self.assertEqual(rows[2]["action"], "malformed_action")

    def test_build_evolution_summary_rows_includes_pass_metrics_and_version(self) -> None:
        snapshot = load_latest_evolution_snapshot(Path("/tmp/does-not-exist"))
        snapshot.daily_report_text = "# Daily report\nEverything looks good."
        snapshot.pass_metrics = {
            "overall": {
                "pass_at_1": {
                    "pass_at_1": 0.75,
                    "total_episodes": 20,
                }
            },
        }
        snapshot.annotations_count = 3
        snapshot.candidates_count = 4
        snapshot.regression_notes_count = 1
        snapshot.harness_meta = {"harness_version": "v12"}

        rows = build_evolution_summary_rows(snapshot)

        self.assertEqual(
            rows,
            [
                {"label": "Latest promoted version", "value": "v12"},
                {"label": "Pass@1", "value": "75%"},
                {"label": "Pass window", "value": "20"},
                {"label": "Annotations", "value": "3"},
                {"label": "Candidates", "value": "4"},
                {"label": "Regression notes", "value": "1"},
                {"label": "Daily report", "value": "# Daily report\nEverything looks good."},
            ],
        )

    def test_build_evolution_summary_rows_handles_malformed_pass_metric(self) -> None:
        snapshot = load_latest_evolution_snapshot(Path("/tmp/does-not-exist"))
        snapshot.pass_metrics = {
            "overall": {
                "pass_at_1": {
                    "pass_at_1": "not-a-float",
                    "total_episodes": 20,
                }
            },
        }
        snapshot.harness_meta = {"harness_version": "v12"}

        rows = build_evolution_summary_rows(snapshot)

        self.assertEqual(rows[1], {"label": "Pass@1", "value": "—"})

    def test_build_offline_evolution_command_points_to_module(self) -> None:
        command = build_offline_evolution_command()

        self.assertEqual(command, ["python3", "-m", "tradeharness.evolution.main"])

    def test_run_safe_command_captures_stdout_stderr_and_exit_code(self) -> None:
        result = run_safe_command(
            [
                "python3",
                "-c",
                "import sys; print('ok'); print('warn', file=sys.stderr); sys.exit(3)",
            ]
        )

        self.assertEqual(result["returncode"], 3)
        self.assertIn("ok", result["stdout"])
        self.assertIn("warn", result["stderr"])

    def test_run_safe_command_returns_failure_result_on_timeout(self) -> None:
        with patch("streamlit_app.subprocess.run", side_effect=TimeoutError("too slow")):
            result = run_safe_command(["python3", "-m", "tradeharness.evolution.main"], timeout_seconds=1)

        self.assertEqual(result["returncode"], 124)
        self.assertEqual(result["stdout"], "")
        self.assertIn("timed out", result["stderr"])

    def test_run_safe_command_returns_failure_result_on_exception(self) -> None:
        with patch("streamlit_app.subprocess.run", side_effect=OSError("cannot execute")):
            result = run_safe_command(["python3", "-m", "tradeharness.evolution.main"])

        self.assertEqual(result["returncode"], 1)
        self.assertEqual(result["stdout"], "")
        self.assertIn("cannot execute", result["stderr"])

    def test_render_safe_ops_runs_manual_offline_evolution_and_shows_success(self) -> None:
        with (
            patch("streamlit_app.st.subheader") as mock_subheader,
            patch("streamlit_app.st.button", return_value=True) as mock_button,
            patch("streamlit_app.build_offline_evolution_command", return_value=["python3", "-m", "tradeharness.evolution.main"]),
            patch(
                "streamlit_app.run_safe_command",
                return_value={"returncode": 0, "stdout": "evolved", "stderr": ""},
            ) as mock_run,
            patch("streamlit_app.st.success") as mock_success,
            patch("streamlit_app.st.error") as mock_error,
            patch("streamlit_app.st.code") as mock_code,
        ):
            render_safe_ops()

        mock_subheader.assert_called_once_with("Safe operator controls")
        mock_button.assert_called_once_with(
            "Run offline evolution now",
            use_container_width=True,
        )
        mock_run.assert_called_once_with(["python3", "-m", "tradeharness.evolution.main"])
        mock_success.assert_called_once_with("Offline evolution completed.")
        mock_error.assert_not_called()
        mock_code.assert_called_once_with("STDOUT:\nevolved", language="text")

    def test_render_safe_ops_shows_stdout_and_stderr_when_both_are_present(self) -> None:
        with (
            patch("streamlit_app.st.subheader"),
            patch("streamlit_app.st.button", return_value=True),
            patch("streamlit_app.build_offline_evolution_command", return_value=["python3", "-m", "tradeharness.evolution.main"]),
            patch(
                "streamlit_app.run_safe_command",
                return_value={"returncode": 0, "stdout": "evolved", "stderr": "warning"},
            ),
            patch("streamlit_app.st.success"),
            patch("streamlit_app.st.error"),
            patch("streamlit_app.st.code") as mock_code,
        ):
            render_safe_ops()

        mock_code.assert_any_call("STDOUT:\nevolved", language="text")
        mock_code.assert_any_call("STDERR:\nwarning", language="text")

    def test_render_safe_ops_shows_failure_with_stderr(self) -> None:
        with (
            patch("streamlit_app.st.subheader"),
            patch("streamlit_app.st.button", return_value=True),
            patch("streamlit_app.build_offline_evolution_command", return_value=["python3", "-m", "tradeharness.evolution.main"]),
            patch(
                "streamlit_app.run_safe_command",
                return_value={"returncode": 1, "stdout": "", "stderr": "failed"},
            ),
            patch("streamlit_app.st.success") as mock_success,
            patch("streamlit_app.st.error") as mock_error,
            patch("streamlit_app.st.code") as mock_code,
        ):
            render_safe_ops()

        mock_success.assert_not_called()
        mock_error.assert_called_once_with("Offline evolution failed.")
        mock_code.assert_called_once_with("STDERR:\nfailed", language="text")

    def test_render_control_panel_saves_live_toggle_change(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            control_path = Path(temp_dir_name) / "state.json"
            state = ControlState(
                live_enabled=False,
                strategy=StrategyControlState(
                    mode="random_flip",
                    entry_quantity_btc=0.008,
                    hold_seconds=120,
                    cooldown_seconds=0,
                ),
            )
            with (
                patch("streamlit_app.st.subheader"),
                patch("streamlit_app.st.caption"),
                patch("streamlit_app.st.warning"),
                patch("streamlit_app.st.info") as mock_info,
                patch("streamlit_app.st.toggle", return_value=True),
                patch("streamlit_app.st.success") as mock_success,
                patch("streamlit_app.st.rerun") as mock_rerun,
                patch("streamlit_app.st.expander", side_effect=[nullcontext(), nullcontext(), nullcontext(), nullcontext()]),
                patch("streamlit_app.st.form"),
                patch("streamlit_app.st.markdown"),
                patch("streamlit_app.st.selectbox", return_value="random_flip"),
                patch("streamlit_app.st.number_input", side_effect=[0.008, 120, 0]),
                patch("streamlit_app.st.form_submit_button", side_effect=[False, False]),
                patch("streamlit_app.render_safe_ops"),
            ):
                render_control_panel(control_path, state)

            saved = load_control_state(control_path)

        self.assertTrue(saved.live_enabled)
        mock_info.assert_called_once()
        mock_success.assert_called_once_with("Live control updated.")
        mock_rerun.assert_called_once_with()

    def test_render_control_panel_saves_risk_guard_change(self) -> None:
        with TemporaryDirectory() as temp_dir_name:
            control_path = Path(temp_dir_name) / "state.json"
            state = ControlState(
                live_enabled=False,
                strategy=StrategyControlState(),
                risk=RiskControlState(
                    max_daily_loss_usdt=50.0,
                    max_open_positions=1,
                    loss_cooldown_seconds=1800,
                    hard_stop_candle_range_pct=2.0,
                ),
            )
            with (
                patch("streamlit_app.st.subheader"),
                patch("streamlit_app.st.caption"),
                patch("streamlit_app.st.warning"),
                patch("streamlit_app.st.info"),
                patch("streamlit_app.st.toggle", return_value=False),
                patch("streamlit_app.st.success") as mock_success,
                patch("streamlit_app.st.rerun") as mock_rerun,
                patch("streamlit_app.st.expander", side_effect=[nullcontext(), nullcontext(), nullcontext(), nullcontext()]),
                patch("streamlit_app.st.form"),
                patch("streamlit_app.st.markdown"),
                patch("streamlit_app.st.selectbox", return_value="manual_only"),
                patch("streamlit_app.st.number_input", side_effect=[0.01, 300, 45, 25.0, 2, 900, 1.5]),
                patch("streamlit_app.st.form_submit_button", side_effect=[False, False, True]),
                patch("streamlit_app.render_safe_ops"),
            ):
                render_control_panel(control_path, state)

            saved = load_control_state(control_path)

        self.assertEqual(saved.strategy.mode, "random_flip")
        self.assertEqual(saved.strategy.entry_quantity_btc, 0.008)
        self.assertEqual(saved.strategy.hold_seconds, 120)
        self.assertEqual(saved.strategy.cooldown_seconds, 0)
        self.assertEqual(saved.risk.max_daily_loss_usdt, 25.0)
        self.assertEqual(saved.risk.max_open_positions, 2)
        self.assertEqual(saved.risk.loss_cooldown_seconds, 900)
        self.assertEqual(saved.risk.hard_stop_candle_range_pct, 1.5)
        mock_success.assert_called_once_with("Risk guard updated.")
        mock_rerun.assert_called_once_with()

    def test_refresh_nonce_helpers_increment_session_state(self) -> None:
        with patch("streamlit_app.st.session_state", {}):
            self.assertEqual(get_refresh_nonce("runtime"), 0)
            self.assertEqual(bump_refresh_nonce("runtime"), 1)
            self.assertEqual(get_refresh_nonce("runtime"), 1)

    def test_main_wires_sections_in_operator_console_order(self) -> None:
        call_order: list[str] = []
        dashboard_paths = {
            "env_path": Path("/tmp/.env"),
            "log_path": Path("/tmp/episodes.jsonl"),
            "evolution_dir": Path("/tmp/evolution"),
            "harness_meta_path": Path("/tmp/harness_meta.json"),
            "control_state_path": Path("/tmp/control/state.json"),
        }

        with (
            patch("streamlit_app.st.set_page_config") as mock_page_config,
            patch("streamlit_app.st.sidebar.header"),
            patch("streamlit_app.st.sidebar.text_input", return_value="/tmp/episodes.jsonl"),
            patch("streamlit_app.st.sidebar.caption"),
            patch(
                "streamlit_app.st.tabs",
                return_value=[nullcontext(), nullcontext(), nullcontext(), nullcontext()],
            ),
            patch("streamlit_app.resolve_dashboard_paths", return_value=dashboard_paths),
            patch("streamlit_app.render_runtime_fragment", side_effect=lambda *_: call_order.append("runtime")),
            patch("streamlit_app.render_evolution_fragment", side_effect=lambda *_: call_order.append("evolution")),
            patch("streamlit_app.render_control_fragment", side_effect=lambda *_: call_order.append("control")),
            patch("streamlit_app.render_debug_fragment", side_effect=lambda *_: call_order.append("debug")),
        ):
            main()

        mock_page_config.assert_called_once_with(
            page_title="TradeHarness Operator Console",
            layout="wide",
        )
        self.assertEqual(
            call_order,
            ["runtime", "control", "evolution", "debug"],
        )


if __name__ == "__main__":
    unittest.main()
