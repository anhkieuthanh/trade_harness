from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from tradeharness.config.settings import load_settings
from tradeharness.evolution.fap.annotator import annotate_episode_failure
from tradeharness.evolution.mining.patterns import mine_failure_patterns
from tradeharness.evolution.storage.artifacts import (
    write_json_artifact,
    write_markdown_report,
)
from tradeharness.evolution.storage.trajectories import load_trajectory_episodes
from tradeharness.evolution.updater.agent import build_update_candidates
from tradeharness.evolution.updater.promotion import build_promotion_report
from tradeharness.evolution.updater.regression import build_regression_note
from tradeharness.evolution.updater.staging import build_staged_layer_artifacts
from tradeharness.integrations.evaluator.client import EvaluatorClient


def build_daily_report_lines(
    *,
    annotations: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> list[str]:
    lines = [
        "# Offline Evolution Daily Report",
        "",
        f"- Episodes analyzed: {len(annotations)}",
        f"- Update candidates: {len(candidates)}",
        "",
        "## Dominant Failure Patterns",
    ]
    if annotations:
        for item in annotations:
            lines.append(
                f"- {item['episode_id']}: {item['primary_failure_type']}"
            )
    else:
        lines.append("- No episodes were available for analysis.")

    lines.extend(["", "## Proposed Updates"])
    if candidates:
        for candidate in candidates:
            lines.append(
                f"- {candidate['target_layer']}: {candidate['suggested_change']}"
            )
    else:
        lines.append("- No update candidates generated.")

    return lines


def run_offline_evolution(
    *,
    trajectory_log_path: str,
    output_dir: str,
    evaluator: Any,
    minimum_support: int = 1,
    active_contract_artifact_path: str = "tradeharness/evolution/artifacts/current/contract.json",
    active_skills_artifact_path: str = "tradeharness/evolution/artifacts/current/skills.json",
) -> dict[str, str]:
    run_id = datetime.now(timezone.utc).isoformat()
    episodes = load_trajectory_episodes(trajectory_log_path)
    annotations = [
        annotate_episode_failure(episode=episode, evaluator=evaluator)
        for episode in episodes
    ]
    patterns = mine_failure_patterns(annotations)
    candidates = build_update_candidates(
        annotations=patterns,
        current_harness={"layers": ["layer_1", "layer_2", "layer_3", "layer_4"]},
        design_guide={},
    )
    regression_notes = [build_regression_note(candidate=item) for item in candidates]
    staged_artifacts = build_staged_layer_artifacts(
        candidates,
        source_run_id=run_id,
    )
    promotion_report = build_promotion_report(
        candidates=candidates,
        regression_notes=regression_notes,
        minimum_support=minimum_support,
    )
    report_lines = build_daily_report_lines(
        annotations=annotations,
        candidates=candidates,
    )

    staging_dir = os.path.join(output_dir, "staging")
    if any(item["decision"]["promote"] for item in promotion_report):
        if staged_artifacts["contract"]["clauses"]:
            write_json_artifact(
                active_contract_artifact_path,
                staged_artifacts["contract"],
            )
        if staged_artifacts["skills"]["skills"]:
            write_json_artifact(
                active_skills_artifact_path,
                staged_artifacts["skills"],
            )

    return {
        "daily_report_path": write_markdown_report(
            os.path.join(output_dir, "daily-report.md"),
            report_lines,
        ),
        "annotations_path": write_json_artifact(
            os.path.join(output_dir, "annotations.json"),
            annotations,
        ),
        "candidates_path": write_json_artifact(
            os.path.join(output_dir, "candidates.json"),
            candidates,
        ),
        "patterns_path": write_json_artifact(
            os.path.join(output_dir, "patterns.json"),
            patterns,
        ),
        "regression_notes_path": write_json_artifact(
            os.path.join(output_dir, "regression-notes.json"),
            regression_notes,
        ),
        "staged_contract_path": write_json_artifact(
            os.path.join(staging_dir, "contract.json"),
            staged_artifacts["contract"],
        ),
        "staged_skills_path": write_json_artifact(
            os.path.join(staging_dir, "skills.json"),
            staged_artifacts["skills"],
        ),
        "staged_action_rules_path": write_json_artifact(
            os.path.join(staging_dir, "action_rules.json"),
            staged_artifacts["action_rules"],
        ),
        "staged_trajectory_rules_path": write_json_artifact(
            os.path.join(staging_dir, "trajectory_rules.json"),
            staged_artifacts["trajectory_rules"],
        ),
        "promotion_report_path": write_json_artifact(
            os.path.join(output_dir, "promotion-report.json"),
            promotion_report,
        ),
        "active_contract_artifact_path": active_contract_artifact_path,
        "active_skills_artifact_path": active_skills_artifact_path,
    }


def main() -> None:
    settings = load_settings()
    evaluator = EvaluatorClient(
        base_url=settings.evaluator_base_url,
        api_key=settings.evaluator_api_key,
        model=settings.evaluator_model,
    )
    result = run_offline_evolution(
        trajectory_log_path=settings.trajectory_log_path,
        output_dir=settings.evolution_output_dir,
        evaluator=evaluator,
        minimum_support=settings.evolution_minimum_support,
        active_contract_artifact_path=settings.active_contract_artifact_path,
        active_skills_artifact_path=settings.active_skills_artifact_path,
    )
    print(result)


if __name__ == "__main__":
    main()
