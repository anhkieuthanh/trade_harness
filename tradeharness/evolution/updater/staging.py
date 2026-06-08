from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _base_payload(source_run_id: str) -> dict[str, Any]:
    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_run_id": source_run_id,
    }


def build_staged_layer_artifacts(
    candidates: list[dict[str, Any]],
    *,
    source_run_id: str,
) -> dict[str, dict[str, Any]]:
    artifacts = {
        "contract": {**_base_payload(source_run_id), "clauses": []},
        "skills": {**_base_payload(source_run_id), "skills": []},
        "action_rules": {**_base_payload(source_run_id), "rules": []},
        "trajectory_rules": {**_base_payload(source_run_id), "rules": []},
    }

    for index, candidate in enumerate(candidates, start=1):
        target_layer = candidate["target_layer"]
        if target_layer == "layer_1":
            artifacts["contract"]["clauses"].append(
                {
                    "id": f"contract-{index}",
                    "priority": 100,
                    "rule_text": candidate["suggested_change"],
                    "trigger_pattern": candidate["problem_pattern"],
                    "supporting_episodes": candidate["supporting_episodes"],
                }
            )
        elif target_layer == "layer_2":
            artifacts["skills"]["skills"].append(
                {
                    "skill_id": f"artifact-skill-{index}",
                    "title": candidate["problem_pattern"].replace("_", " ").title(),
                    "tags": [candidate["problem_pattern"], "evolution"],
                    "when_to_use": f"When pattern {candidate['problem_pattern']} is recurring.",
                    "procedure": candidate["suggested_change"],
                    "anti_patterns": "Do not ignore the repeated failure evidence.",
                    "source_episodes": candidate["supporting_episodes"],
                }
            )
        elif target_layer == "layer_3":
            artifacts["action_rules"]["rules"].append(
                {
                    "rule_id": f"action-rule-{index}",
                    "tool_name": "dynamic",
                    "condition": candidate["problem_pattern"],
                    "decision": "BLOCK",
                    "message": candidate["suggested_change"],
                    "supporting_episodes": candidate["supporting_episodes"],
                }
            )
        elif target_layer == "layer_4":
            artifacts["trajectory_rules"]["rules"].append(
                {
                    "rule_id": f"trajectory-rule-{index}",
                    "pattern_type": candidate["problem_pattern"],
                    "window": 5,
                    "threshold": 3,
                    "decision": "WARN",
                    "message": candidate["suggested_change"],
                    "supporting_episodes": candidate["supporting_episodes"],
                }
            )

    return artifacts
