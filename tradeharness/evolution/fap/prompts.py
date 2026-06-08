from __future__ import annotations

import json
from typing import Any


FAP_GATES = [
    "action_realization",
    "environment_contract",
    "trajectory_degeneration",
    "residual_reasoning",
]


def build_fap_gate_prompt(*, gate_name: str, episode: dict[str, Any]) -> str:
    return (
        f"You are evaluating only the {gate_name} gate.\n"
        "Return whether this gate matches. Do not choose any other gate.\n"
        "Respond with strict JSON only using this schema:\n"
        '{"matched": true|false, "failed_step_index": 0, "evidence": ["..."], "rationale": "..."}\n'
        "If the gate does not match, return matched=false and keep the other fields minimal.\n"
        f"Episode:\n{json.dumps(episode, indent=2, sort_keys=True)}"
    )
