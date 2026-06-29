from __future__ import annotations

import json
from typing import Any

from tradeharness.evolution.fap.prompts import FAP_GATES, build_fap_gate_prompt
from tradeharness.evolution.schemas import build_annotation_record


def _strip_code_fences(content: str) -> str:
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return content


def _normalize_evaluator_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict) and "matched" in result:
        return {
            "matched": bool(result.get("matched")),
            "failed_step_index": int(result.get("failed_step_index", 0) or 0),
            "evidence": list(result.get("evidence", [])),
            "rationale": str(result.get("rationale", "")),
        }

    if isinstance(result, dict) and "choices" in result:
        message = result["choices"][0]["message"]
        content = _strip_code_fences(str(message.get("content", "")).strip())
        if not content:
            return {
                "matched": False,
                "failed_step_index": 0,
                "evidence": [],
                "rationale": "",
            }
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return {
                "matched": False,
                "failed_step_index": 0,
                "evidence": [],
                "rationale": content,
            }
        return {
            "matched": bool(payload.get("matched")),
            "failed_step_index": int(payload.get("failed_step_index", 0) or 0),
            "evidence": list(payload.get("evidence", [])),
            "rationale": str(payload.get("rationale", "")),
        }

    return {
        "matched": False,
        "failed_step_index": 0,
        "evidence": [],
        "rationale": "",
    }


def _fallback_annotate(episode: dict[str, Any], error: Exception) -> dict[str, Any]:
    reason = str(episode.get("termination_reason") or "")
    if "action_realization" in reason:
        primary = "action_realization"
    elif "environment_contract" in reason:
        primary = "environment_contract"
    elif "trajectory_degeneration" in reason or "trajectory_regulation" in reason:
        primary = "trajectory_degeneration"
    else:
        primary = "residual_reasoning"

    priority_checks = [{"type": gate, "matched": (gate == primary)} for gate in FAP_GATES]
    return build_annotation_record(
        episode_id=episode["episode_id"],
        primary_failure_type=primary,
        failed_step_index=0,
        priority_checks=priority_checks,
        evidence=[],
        rationale=f"Evaluator failed ({error.__class__.__name__}: {error}). Fallback rule selected: {primary}.",
    )


def annotate_episode_failure(
    *,
    episode: dict[str, Any],
    evaluator: Any,
) -> dict[str, Any]:
    priority_checks: list[dict[str, Any]] = []

    for gate_name in FAP_GATES:
        try:
            raw_result = evaluator.complete(
                system_prompt="You are a strict failure annotation evaluator.",
                user_prompt=build_fap_gate_prompt(gate_name=gate_name, episode=episode),
            )
            result = _normalize_evaluator_result(raw_result)
        except Exception as exc:
            print(f"Evaluator error on gate {gate_name}: {exc}. Triggering fallback annotator.")
            return _fallback_annotate(episode, exc)

        matched = bool(result.get("matched"))
        priority_checks.append({"type": gate_name, "matched": matched})
        if matched:
            return build_annotation_record(
                episode_id=episode["episode_id"],
                primary_failure_type=gate_name,
                failed_step_index=result.get("failed_step_index", 0),
                priority_checks=priority_checks,
                evidence=result.get("evidence", []),
                rationale=result.get("rationale", ""),
            )

    return build_annotation_record(
        episode_id=episode["episode_id"],
        primary_failure_type="residual_reasoning",
        failed_step_index=0,
        priority_checks=priority_checks,
        evidence=[],
        rationale="Reached residual reasoning after all higher-priority gates failed.",
    )

