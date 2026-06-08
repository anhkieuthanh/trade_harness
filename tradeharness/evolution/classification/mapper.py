from __future__ import annotations


LAYER_TARGETS = {
    "action_realization": "layer_3",
    "environment_contract": "layer_1",
    "trajectory_degeneration": "layer_4",
    "residual_reasoning": "layer_2",
}


def map_failure_to_layer(failure_type: str) -> str:
    return LAYER_TARGETS[failure_type]
