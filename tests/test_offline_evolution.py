from __future__ import annotations

import json
import os
import tempfile
import unittest

from tradeharness.config.settings import load_settings
from tradeharness.evolution.classification.mapper import map_failure_to_layer
from tradeharness.evolution.fap.annotator import annotate_episode_failure
from tradeharness.evolution.fap.prompts import build_fap_gate_prompt
from tradeharness.evolution.main import run_offline_evolution
from tradeharness.evolution.metrics import (
    summarize_pass_metrics,
    summarize_pass_metrics_by_harness_version,
)
from tradeharness.evolution.mining.patterns import mine_failure_patterns
from tradeharness.evolution.scheduler import build_run_output_dir
from tradeharness.evolution.schemas import (
    build_annotation_record,
    build_episode_record,
    build_step_record,
    build_update_candidate,
)
from tradeharness.evolution.storage.trajectories import append_episode_record
from tradeharness.evolution.updater.agent import build_update_candidates
from tradeharness.evolution.updater.promotion import should_promote_candidate
from tradeharness.evolution.updater.prompting import build_evolution_system_prompt
from tradeharness.evolution.updater.regression import build_regression_note
from tradeharness.evolution.updater.staging import build_staged_layer_artifacts
from tradeharness.evolution.versioning import build_next_harness_meta
from tradeharness.integrations.evaluator.client import EvaluatorClient
from tradeharness.runtime.contracts.environment import build_environment_contract
from tradeharness.runtime.agent import (
    build_episode_termination_record,
    build_runtime_step_record,
)
from tradeharness.runtime.skills.library import get_skill_library


class EvolutionSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_env = os.environ.copy()
        os.environ.setdefault("BINANCE_API_KEY", "test-key")
        os.environ.setdefault("BINANCE_API_SECRET", "test-secret")

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._original_env)

    def test_build_step_record_includes_required_fields(self) -> None:
        record = build_step_record(
            step_index=1,
            observation={"price": 63000.0},
            decision_summary="Inspecting before entry.",
            action={"tool": "get_position", "arguments": {"symbol": "BTCUSDT"}},
            harness_intervention={"decision": "EXECUTE", "layer": "none"},
            environment_feedback={"position_side": "FLAT"},
        )

        self.assertEqual(record["step_index"], 1)
        self.assertIn("observation", record)
        self.assertIn("decision_summary", record)
        self.assertIn("action", record)
        self.assertIn("harness_intervention", record)
        self.assertIn("environment_feedback", record)

    def test_build_episode_record_wraps_steps_and_outcome(self) -> None:
        step = build_step_record(
            step_index=1,
            observation={"price": 63000.0},
            decision_summary="Inspecting before entry.",
            action={"tool": "get_position", "arguments": {"symbol": "BTCUSDT"}},
            harness_intervention={"decision": "EXECUTE", "layer": "none"},
            environment_feedback={"position_side": "FLAT"},
        )

        episode = build_episode_record(
            episode_id="episode-1",
            task_id="task-1",
            harness_version="v1",
            symbol="BTCUSDT",
            mode="demo",
            started_at="2026-06-08T00:00:00Z",
            ended_at="2026-06-08T00:01:00Z",
            final_status="FAILED",
            termination_reason="blocked_by_action_realization_limit",
            steps=[step],
            final_outcome={"final": "blocked"},
        )

        self.assertEqual(episode["episode_id"], "episode-1")
        self.assertEqual(episode["task_id"], "task-1")
        self.assertEqual(episode["harness_version"], "v1")
        self.assertEqual(len(episode["steps"]), 1)
        self.assertEqual(
            episode["termination_reason"],
            "blocked_by_action_realization_limit",
        )

    def test_build_annotation_record_returns_payload_copy(self) -> None:
        payload = {"failure_gate": "entry", "label": "late_confirmation"}

        record = build_annotation_record(**payload)

        self.assertEqual(record, payload)
        self.assertIsNot(record, payload)

    def test_build_update_candidate_returns_payload_copy(self) -> None:
        payload = {"layer": "strategy", "proposal": "tighten entry checklist"}

        record = build_update_candidate(**payload)

        self.assertEqual(record, payload)
        self.assertIsNot(record, payload)

    def test_load_settings_reads_evaluator_configuration(self) -> None:
        settings = load_settings()

        self.assertTrue(hasattr(settings, "evaluator_base_url"))
        self.assertTrue(hasattr(settings, "evaluator_api_key"))
        self.assertTrue(hasattr(settings, "trajectory_log_path"))

    def test_load_settings_prefers_harness_meta_version_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            meta_path = os.path.join(temp_dir, "harness_meta.json")
            with open(meta_path, "w", encoding="utf-8") as handle:
                json.dump({"harness_version": "v7"}, handle)

            os.environ["ACTIVE_HARNESS_META_ARTIFACT_PATH"] = meta_path
            os.environ["HARNESS_VERSION"] = "manual-fallback"

            settings = load_settings()

        self.assertEqual(settings.harness_version, "v7")
        self.assertEqual(settings.active_harness_meta_artifact_path, meta_path)


class RuntimeTrajectoryLoggingTests(unittest.TestCase):
    def test_build_runtime_step_record_captures_required_step_fields(self) -> None:
        record = build_runtime_step_record(
            step_index=2,
            observation={"price": 63100.0},
            decision_summary="Need one more balance check.",
            action={"tool": "get_balance", "arguments": {"asset": "USDT"}},
            harness_intervention={"decision": "WARN", "layer": "trajectory_regulation"},
            environment_feedback={"available_balance": 1000.0},
        )

        self.assertEqual(record["step_index"], 2)
        self.assertEqual(record["action"]["tool"], "get_balance")
        self.assertEqual(record["harness_intervention"]["decision"], "WARN")

    def test_build_episode_termination_record_includes_final_status(self) -> None:
        record = build_episode_termination_record(
            episode_id="episode-1",
            task_id="task-1",
            harness_version="v1",
            symbol="BTCUSDT",
            mode="demo",
            started_at="2026-06-08T00:00:00Z",
            ended_at="2026-06-08T00:01:00Z",
            steps=[],
            final_status="FAILED",
            termination_reason="trajectory_regulation_stop",
            final_outcome={"final": "trajectory_regulation_stop"},
        )

        self.assertEqual(record["episode_id"], "episode-1")
        self.assertEqual(record["task_id"], "task-1")
        self.assertEqual(record["harness_version"], "v1")
        self.assertEqual(record["mode"], "demo")
        self.assertEqual(record["final_status"], "FAILED")

    def test_append_episode_record_writes_one_json_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "episodes.jsonl")
            append_episode_record(
                path,
                {"episode_id": "episode-1", "steps": [], "final_status": "FAILED"},
            )

            with open(path, "r", encoding="utf-8") as handle:
                lines = handle.readlines()

        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["episode_id"], "episode-1")


class EvaluatorClientTests(unittest.TestCase):
    def test_build_payload_uses_openai_compatible_shape(self) -> None:
        client = EvaluatorClient(
            base_url="https://api.example.com/v1",
            api_key="secret",
            model="gpt-5.4",
        )

        payload = client.build_payload(
            system_prompt="system",
            user_prompt="user",
        )

        self.assertEqual(payload["model"], "gpt-5.4")
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][1]["role"], "user")
        self.assertEqual(payload["temperature"], 0)


class FailurePatternMiningTests(unittest.TestCase):
    def test_mine_failure_patterns_groups_repeated_annotation_signatures(self) -> None:
        patterns = mine_failure_patterns(
            [
                {
                    "episode_id": "ep-1",
                    "primary_failure_type": "environment_contract",
                    "evidence": ["tool=get_balance", "argument=BTCUSDT"],
                },
                {
                    "episode_id": "ep-2",
                    "primary_failure_type": "environment_contract",
                    "evidence": ["tool=get_balance", "argument=BTCUSDT"],
                },
            ]
        )

        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0]["frequency"], 2)
        self.assertEqual(patterns[0]["target_layer"], "layer_1")


class PassMetricsTests(unittest.TestCase):
    def test_summarize_pass_metrics_returns_pass_at_1(self) -> None:
        episodes = [
            {
                "episode_id": "ep-1",
                "harness_version": "v1",
                "final_status": "SUCCESS",
                "started_at": "2026-06-08T00:00:00Z",
            },
            {
                "episode_id": "ep-2",
                "harness_version": "v1",
                "final_status": "SUCCESS",
                "started_at": "2026-06-08T00:01:00Z",
            },
            {
                "episode_id": "ep-3",
                "harness_version": "v1",
                "final_status": "SUCCESS",
                "started_at": "2026-06-08T00:02:00Z",
            },
            {
                "episode_id": "ep-4",
                "harness_version": "v2",
                "final_status": "FAILED",
                "started_at": "2026-06-08T00:03:00Z",
            },
        ]

        summary = summarize_pass_metrics(episodes)

        self.assertEqual(summary["pass_at_1"]["total_episodes"], 4)
        self.assertEqual(summary["pass_at_1"]["passed_episodes"], 3)
        self.assertAlmostEqual(summary["pass_at_1"]["pass_at_1"], 0.75)

    def test_summarize_pass_metrics_by_harness_version_groups_versions(self) -> None:
        summary = summarize_pass_metrics_by_harness_version(
            [
                {
                    "episode_id": "ep-1",
                    "harness_version": "v1",
                    "final_status": "SUCCESS",
                    "started_at": "2026-06-08T00:00:00Z",
                },
                {
                    "episode_id": "ep-2",
                    "harness_version": "v1",
                    "final_status": "FAILED",
                    "started_at": "2026-06-08T00:01:00Z",
                },
                {
                    "episode_id": "ep-3",
                    "harness_version": "v2",
                    "final_status": "SUCCESS",
                    "started_at": "2026-06-08T00:02:00Z",
                },
            ]
        )

        self.assertEqual(summary[0]["harness_version"], "v1")
        self.assertAlmostEqual(summary[0]["pass_at_1"], 0.5)
        self.assertEqual(summary[1]["harness_version"], "v2")
        self.assertAlmostEqual(summary[1]["pass_at_1"], 1.0)


class FAPAnnotatorTests(unittest.TestCase):
    def test_build_fap_gate_prompt_mentions_only_requested_gate(self) -> None:
        prompt = build_fap_gate_prompt(
            gate_name="action_realization",
            episode={"episode_id": "episode-1", "steps": []},
        )

        self.assertIn("action_realization", prompt.lower())
        self.assertIn("do not choose any other gate", prompt.lower())
        self.assertIn("respond with strict json only", prompt.lower())

    def test_annotate_episode_failure_stops_at_first_matching_gate(self) -> None:
        class FakeEvaluator:
            def complete(self, *, system_prompt: str, user_prompt: str):
                if "action_realization" in user_prompt:
                    return {
                        "matched": True,
                        "failed_step_index": 2,
                        "evidence": ["plain text instead of tool"],
                        "rationale": "Malformed action expression.",
                    }
                return {"matched": False, "evidence": []}

        annotation = annotate_episode_failure(
            episode={"episode_id": "episode-1", "steps": []},
            evaluator=FakeEvaluator(),
        )

        self.assertEqual(annotation["primary_failure_type"], "action_realization")
        self.assertEqual(annotation["priority_checks"][0]["matched"], True)
        self.assertEqual(annotation["failed_step_index"], 2)

    def test_annotate_episode_failure_parses_openai_style_json_content(self) -> None:
        class FakeEvaluator:
            def complete(self, *, system_prompt: str, user_prompt: str):
                if "action_realization" in user_prompt:
                    return {
                        "choices": [
                            {
                                "message": {
                                    "content": '```json\n{"matched": true, "failed_step_index": 3, "evidence": ["missing tool call"], "rationale": "The agent replied in prose instead of a tool request."}\n```'
                                }
                            }
                        ]
                    }
                return {
                    "choices": [
                        {
                            "message": {
                                "content": '{"matched": false, "failed_step_index": 0, "evidence": [], "rationale": ""}'
                            }
                        }
                    ]
                }

        annotation = annotate_episode_failure(
            episode={"episode_id": "episode-2", "steps": []},
            evaluator=FakeEvaluator(),
        )

        self.assertEqual(annotation["primary_failure_type"], "action_realization")
        self.assertEqual(annotation["failed_step_index"], 3)
        self.assertIn("missing tool call", annotation["evidence"])


class EvolutionUpdaterTests(unittest.TestCase):
    def test_map_failure_to_layer_uses_expected_life_harness_target(self) -> None:
        self.assertEqual(map_failure_to_layer("action_realization"), "layer_3")
        self.assertEqual(map_failure_to_layer("environment_contract"), "layer_1")
        self.assertEqual(map_failure_to_layer("trajectory_degeneration"), "layer_4")
        self.assertEqual(map_failure_to_layer("residual_reasoning"), "layer_2")

    def test_build_update_candidates_limits_to_top_two_patterns(self) -> None:
        candidates = build_update_candidates(
            annotations=[
                {"primary_failure_type": "action_realization", "episode_id": "a"},
                {"primary_failure_type": "action_realization", "episode_id": "b"},
                {"primary_failure_type": "environment_contract", "episode_id": "c"},
            ],
            current_harness={"layers": ["layer_1", "layer_2", "layer_3", "layer_4"]},
            design_guide={"layer_3": "May block or canonicalize actions."},
        )

        self.assertLessEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["target_layer"], "layer_3")

    def test_build_evolution_system_prompt_mentions_core_guardrails(self) -> None:
        prompt = build_evolution_system_prompt(
            harness_dir="/tmp/harness",
            trajectory_dir="/tmp/trajectories",
            design_guide="Layer 3 only blocks or canonicalizes unambiguous interface errors.",
        )

        self.assertIn("runtime harness", prompt.lower())
        self.assertIn("do not use test labels", prompt.lower())
        self.assertIn("/tmp/harness", prompt)
        self.assertIn("four lifecycle layers", prompt.lower())
        self.assertIn("remaining failure modes", prompt.lower())

    def test_build_regression_note_flags_overtrigger_risk_for_blocking_layers(self) -> None:
        note = build_regression_note(
            candidate={"target_layer": "layer_3", "suggested_change": "Add stricter validator."}
        )

        self.assertIn("over-trigger", note["risk_summary"].lower())


class StagingAndPromotionTests(unittest.TestCase):
    def test_build_staged_layer_artifacts_splits_candidates_by_layer(self) -> None:
        artifacts = build_staged_layer_artifacts(
            [
                {
                    "target_layer": "layer_1",
                    "problem_pattern": "environment_contract",
                    "suggested_change": "Add stricter contract clauses and tool guidance in Layer 1.",
                    "supporting_episodes": ["ep-1"],
                },
                {
                    "target_layer": "layer_2",
                    "problem_pattern": "residual_reasoning",
                    "suggested_change": "Add a new distilled procedural skill to Layer 2.",
                    "supporting_episodes": ["ep-2"],
                },
            ],
            source_run_id="2026-06-08",
        )

        self.assertIn("contract", artifacts)
        self.assertIn("skills", artifacts)
        self.assertEqual(len(artifacts["contract"]["clauses"]), 1)
        self.assertEqual(len(artifacts["skills"]["skills"]), 1)

    def test_should_promote_candidate_blocks_high_overtrigger_risk(self) -> None:
        decision = should_promote_candidate(
            candidate={"target_layer": "layer_3", "supporting_episodes": ["a"]},
            regression_note={"flags": ["high_overtrigger_risk"]},
            minimum_support=1,
        )

        self.assertFalse(decision["promote"])

    def test_build_next_harness_meta_increments_semver_like_revision(self) -> None:
        next_meta = build_next_harness_meta(
            current_meta={"harness_version": "v4"},
            source_run_id="2026-06-08T00:00:00+00:00",
        )

        self.assertEqual(next_meta["harness_version"], "v5")
        self.assertEqual(next_meta["revision"], 5)
        self.assertEqual(next_meta["previous_harness_version"], "v4")


class EvolutionSchedulerTests(unittest.TestCase):
    def test_build_run_output_dir_appends_date_partition(self) -> None:
        result = build_run_output_dir(
            base_dir="var/evolution/runs",
            run_date="2026-06-08",
        )
        self.assertTrue(result.endswith("var/evolution/runs/2026-06-08"))


class RuntimeArtifactRehydrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original_env = os.environ.copy()

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._original_env)

    def test_environment_contract_includes_active_contract_artifact_clause(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "contract.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "clauses": [
                            {"rule_text": "Artifact rule: prefer explicit asset names for balance checks."}
                        ]
                    },
                    handle,
                )
            os.environ["ACTIVE_CONTRACT_ARTIFACT_PATH"] = path
            contract = build_environment_contract(symbol="BTCUSDT")

        self.assertIn("Artifact rule", contract)

    def test_skill_library_includes_active_skill_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "skills.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "skills": [
                            {
                                "skill_id": "artifact_skill",
                                "title": "Artifact skill",
                                "tags": ["artifact"],
                                "when_to_use": "When loaded from active artifact.",
                                "procedure": "Follow the staged procedure.",
                                "anti_patterns": "Do not ignore the artifact.",
                            }
                        ]
                    },
                    handle,
                )
            os.environ["ACTIVE_SKILLS_ARTIFACT_PATH"] = path
            skills = get_skill_library()

        self.assertTrue(any(item["skill_id"] == "artifact_skill" for item in skills))


class OfflineEvolutionMainTests(unittest.TestCase):
    def test_run_offline_evolution_returns_named_artifact_paths(self) -> None:
        class FakeEvaluator:
            def complete(self, *, system_prompt: str, user_prompt: str):
                return {"matched": False, "evidence": []}

        with tempfile.TemporaryDirectory() as temp_dir:
            trajectory_log_path = os.path.join(temp_dir, "episodes.jsonl")
            output_dir = os.path.join(temp_dir, "evolution")
            append_episode_record(
                trajectory_log_path,
                {
                    "episode_id": "episode-1",
                    "task_id": "task-1",
                    "harness_version": "v1",
                    "symbol": "BTCUSDT",
                    "mode": "demo",
                    "started_at": "2026-06-08T00:00:00Z",
                    "ended_at": "2026-06-08T00:01:00Z",
                    "final_status": "FAILED",
                    "termination_reason": "blocked",
                    "steps": [],
                    "final_outcome": {"final": "blocked"},
                },
            )

            result = run_offline_evolution(
                trajectory_log_path=trajectory_log_path,
                output_dir=output_dir,
                evaluator=FakeEvaluator(),
                active_harness_meta_artifact_path=os.path.join(
                    temp_dir,
                    "current",
                    "harness_meta.json",
                ),
            )

            self.assertIn("daily_report_path", result)
            self.assertIn("annotations_path", result)
            self.assertIn("candidates_path", result)
            self.assertIn("regression_notes_path", result)
            self.assertIn("patterns_path", result)
            self.assertIn("promotion_report_path", result)
            self.assertIn("pass_metrics_path", result)
            self.assertIn("staged_contract_path", result)
            self.assertIn("active_contract_artifact_path", result)
            self.assertIn("active_skills_artifact_path", result)
            self.assertIn("active_harness_meta_artifact_path", result)
            self.assertTrue(os.path.exists(result["annotations_path"]))
            self.assertTrue(os.path.exists(result["active_contract_artifact_path"]))
            self.assertTrue(os.path.exists(result["pass_metrics_path"]))
            self.assertTrue(os.path.exists(result["active_harness_meta_artifact_path"]))

            with open(result["daily_report_path"], "r", encoding="utf-8") as handle:
                report = handle.read()

            self.assertIn("Pass@1", report)
            self.assertIn("Harness Version Metrics", report)

            with open(
                result["active_harness_meta_artifact_path"],
                "r",
                encoding="utf-8",
            ) as handle:
                harness_meta = json.load(handle)

            self.assertEqual(harness_meta["harness_version"], "v1")


if __name__ == "__main__":
    unittest.main()
