from __future__ import annotations

import os
from datetime import datetime, timezone

from tradeharness.config.settings import load_settings
from tradeharness.evolution.main import run_offline_evolution
from tradeharness.integrations.evaluator.client import EvaluatorClient


def build_run_output_dir(*, base_dir: str, run_date: str) -> str:
    return os.path.join(base_dir, run_date)


def main() -> None:
    settings = load_settings()
    run_date = datetime.now(timezone.utc).date().isoformat()
    output_dir = build_run_output_dir(
        base_dir=settings.evolution_runs_dir,
        run_date=run_date,
    )
    evaluator = EvaluatorClient(
        base_url=settings.evaluator_base_url,
        api_key=settings.evaluator_api_key,
        model=settings.evaluator_model,
    )
    result = run_offline_evolution(
        trajectory_log_path=settings.trajectory_log_path,
        output_dir=output_dir,
        evaluator=evaluator,
        minimum_support=settings.evolution_minimum_support,
        active_contract_artifact_path=settings.active_contract_artifact_path,
        active_skills_artifact_path=settings.active_skills_artifact_path,
        active_harness_meta_artifact_path=settings.active_harness_meta_artifact_path,
    )
    print(result)


if __name__ == "__main__":
    main()
