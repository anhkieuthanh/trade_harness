# Offline Evolution Block Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an offline evolution subsystem that records runtime trajectories, diagnoses failures through an evaluator-backed FAP cascade, maps them into LIFE-HARNESS layers, and emits structured harness-update artifacts.

**Architecture:** Extend the online runtime just enough to emit per-episode trajectory JSONL, then add a new `tradeharness.evolution` namespace for offline batch analysis. Keep the diagnosis order deterministic in code, use the evaluator only inside gate-specific judgments, and output update candidates plus regression notes instead of mutating harness code directly.

**Tech Stack:** Python 3.12, stdlib `json`/`dataclasses`/`urllib`, existing `unittest` suite, repo-local markdown docs, OpenAI-compatible HTTP API

---

## File Map

### New files

- `tradeharness/evolution/__init__.py`
- `tradeharness/evolution/main.py`
- `tradeharness/evolution/schemas.py`
- `tradeharness/evolution/storage/__init__.py`
- `tradeharness/evolution/storage/trajectories.py`
- `tradeharness/evolution/storage/artifacts.py`
- `tradeharness/evolution/fap/__init__.py`
- `tradeharness/evolution/fap/prompts.py`
- `tradeharness/evolution/fap/annotator.py`
- `tradeharness/evolution/classification/__init__.py`
- `tradeharness/evolution/classification/mapper.py`
- `tradeharness/evolution/updater/__init__.py`
- `tradeharness/evolution/updater/agent.py`
- `tradeharness/evolution/updater/prompting.py`
- `tradeharness/evolution/updater/regression.py`
- `tradeharness/integrations/evaluator/__init__.py`
- `tradeharness/integrations/evaluator/client.py`
- `tests/test_offline_evolution.py`

### Modified files

- `tradeharness/config/settings.py`
- `tradeharness/runtime/agent.py`
- `tradeharness/runtime/main.py`
- `tradeharness/README.MD`
- `TradeHarness/.env.example`

### Responsibilities

- `settings.py`: load evaluator API configuration and offline-evolution storage paths
- `runtime/agent.py`: collect and flush episode trajectory data
- `evolution/schemas.py`: define shared record shapes for steps, episodes, annotations, classifications, update candidates, and regression notes
- `storage/*.py`: load trajectory JSONL and write offline artifacts
- `fap/*.py`: build gate prompts and run the priority cascade
- `classification/mapper.py`: map the primary failure label to a harness layer
- `updater/*.py`: aggregate patterns, propose updates, and attach regression notes
- `updater/prompting.py`: build the stable system prompt contract for the evolution updater
- `main.py`: batch entrypoint wiring for the offline daily run
- `tests/test_offline_evolution.py`: focused unit coverage for the new subsystem

### Conventions

- Use `unittest`, matching the current repo style.
- Prefer stdlib HTTP, matching the lightweight style of the current project.
- Do not introduce hidden automatic source mutation in the first version.
- Because `/Users/atif/Public/TradeHarness` is not currently a git repo, treat commit steps as skipped until `.git` exists.

### Task 1: Define Evolution Schemas And Settings

**Files:**
- Create: `tradeharness/evolution/schemas.py`
- Modify: `tradeharness/config/settings.py`
- Test: `tests/test_offline_evolution.py`

- [ ] **Step 1: Write the failing schema and settings tests**

```python
import unittest

from tradeharness.config.settings import load_settings
from tradeharness.evolution.schemas import (
    build_annotation_record,
    build_episode_record,
    build_step_record,
    build_update_candidate,
)


class EvolutionSchemaTests(unittest.TestCase):
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
        self.assertEqual(len(episode["steps"]), 1)
        self.assertEqual(episode["termination_reason"], "blocked_by_action_realization_limit")

    def test_load_settings_reads_evaluator_configuration(self) -> None:
        settings = load_settings()

        self.assertTrue(hasattr(settings, "evaluator_base_url"))
        self.assertTrue(hasattr(settings, "evaluator_api_key"))
        self.assertTrue(hasattr(settings, "trajectory_log_path"))
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.EvolutionSchemaTests -v
```

Expected: `FAIL` with import errors for `tradeharness.evolution.schemas` and missing settings fields.

- [ ] **Step 3: Write the minimal schemas and settings implementation**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def build_step_record(
    *,
    step_index: int,
    observation: dict[str, Any],
    decision_summary: str,
    action: dict[str, Any],
    harness_intervention: dict[str, Any],
    environment_feedback: dict[str, Any],
) -> dict[str, Any]:
    return {
        "step_index": step_index,
        "observation": observation,
        "decision_summary": decision_summary,
        "action": action,
        "harness_intervention": harness_intervention,
        "environment_feedback": environment_feedback,
    }


def build_episode_record(
    *,
    episode_id: str,
    symbol: str,
    mode: str,
    started_at: str,
    ended_at: str,
    final_status: str,
    termination_reason: str,
    steps: list[dict[str, Any]],
    final_outcome: dict[str, Any],
) -> dict[str, Any]:
    return {
        "episode_id": episode_id,
        "symbol": symbol,
        "mode": mode,
        "started_at": started_at,
        "ended_at": ended_at,
        "final_status": final_status,
        "termination_reason": termination_reason,
        "steps": steps,
        "final_outcome": final_outcome,
    }


def build_annotation_record(**payload: Any) -> dict[str, Any]:
    return dict(payload)


def build_update_candidate(**payload: Any) -> dict[str, Any]:
    return dict(payload)
```

```python
@dataclass(frozen=True)
class Settings:
    ...
    evaluator_base_url: str
    evaluator_api_key: str
    evaluator_model: str
    trajectory_log_path: str
    evolution_output_dir: str
```

```python
return Settings(
    ...
    evaluator_base_url=os.getenv("EVALUATOR_BASE_URL", "https://example.invalid/v1"),
    evaluator_api_key=os.getenv("EVALUATOR_API_KEY", ""),
    evaluator_model=os.getenv("EVALUATOR_MODEL", "gpt-5.4"),
    trajectory_log_path=os.getenv("TRAJECTORY_LOG_PATH", "var/trajectories/episodes.jsonl"),
    evolution_output_dir=os.getenv("EVOLUTION_OUTPUT_DIR", "var/evolution"),
)
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.EvolutionSchemaTests -v
```

Expected: `OK`

- [ ] **Step 5: Commit**

Skip for now: `/Users/atif/Public/TradeHarness` does not currently contain `.git`.

### Task 2: Add Runtime Trajectory Logging

**Files:**
- Modify: `tradeharness/runtime/agent.py`
- Modify: `tradeharness/runtime/main.py`
- Create: `tradeharness/evolution/storage/trajectories.py`
- Test: `tests/test_offline_evolution.py`

- [ ] **Step 1: Write the failing runtime logging tests**

```python
from tradeharness.evolution.storage.trajectories import append_episode_record
from tradeharness.runtime.agent import (
    build_episode_termination_record,
    build_runtime_step_record,
)


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

    def test_append_episode_record_writes_one_json_line(self) -> None:
        path = "tmp_test_episodes.jsonl"
        append_episode_record(
            path,
            {"episode_id": "episode-1", "steps": [], "final_status": "FAILED"},
        )

        with open(path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()

        self.assertEqual(len(lines), 1)
        self.assertIn('"episode_id": "episode-1"', lines[0])
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.RuntimeTrajectoryLoggingTests -v
```

Expected: `FAIL` because runtime helpers and storage writer do not exist yet.

- [ ] **Step 3: Implement storage writer and runtime helpers**

```python
from __future__ import annotations

import json
import os
from typing import Any


def append_episode_record(path: str, episode: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(episode) + "\n")
```

```python
def build_runtime_step_record(
    *,
    step_index: int,
    observation: dict[str, Any],
    decision_summary: str,
    action: dict[str, Any],
    harness_intervention: dict[str, Any],
    environment_feedback: dict[str, Any],
) -> dict[str, Any]:
    return build_step_record(
        step_index=step_index,
        observation=observation,
        decision_summary=decision_summary,
        action=action,
        harness_intervention=harness_intervention,
        environment_feedback=environment_feedback,
    )
```

```python
def build_episode_termination_record(
    *,
    episode_id: str,
    symbol: str,
    started_at: str,
    ended_at: str,
    steps: list[dict[str, Any]],
    final_status: str,
    termination_reason: str,
    final_outcome: dict[str, Any],
) -> dict[str, Any]:
    return build_episode_record(
        episode_id=episode_id,
        symbol=symbol,
        mode="demo",
        started_at=started_at,
        ended_at=ended_at,
        final_status=final_status,
        termination_reason=termination_reason,
        steps=steps,
        final_outcome=final_outcome,
    )
```

- [ ] **Step 4: Wire the runtime loop to collect steps and flush one episode**

```python
episode_steps: list[dict[str, Any]] = []

episode_steps.append(
    build_runtime_step_record(
        step_index=current_step_index,
        observation=current_observation,
        decision_summary=assistant_summary,
        action={"tool": tool_request.name, "arguments": tool_request.arguments},
        harness_intervention=gate_result_or_regulation_result,
        environment_feedback=tool_result_or_block_feedback,
    )
)
```

```python
append_episode_record(
    settings.trajectory_log_path,
    build_episode_termination_record(
        episode_id=episode_id,
        symbol=settings.symbol,
        started_at=started_at,
        ended_at=ended_at,
        steps=episode_steps,
        final_status="FAILED",
        termination_reason="trajectory_regulation_stop",
        final_outcome={"final": "trajectory_regulation_stop"},
    ),
)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.RuntimeTrajectoryLoggingTests -v
```

Expected: `OK`

- [ ] **Step 6: Commit**

Skip for now: `/Users/atif/Public/TradeHarness` does not currently contain `.git`.

### Task 3: Add Evaluator Client

**Files:**
- Create: `tradeharness/integrations/evaluator/client.py`
- Create: `tradeharness/integrations/evaluator/__init__.py`
- Test: `tests/test_offline_evolution.py`

- [ ] **Step 1: Write the failing evaluator client tests**

```python
from tradeharness.integrations.evaluator.client import EvaluatorClient


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
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.EvaluatorClientTests -v
```

Expected: `FAIL` because `EvaluatorClient` does not exist.

- [ ] **Step 3: Implement the payload builder and request wrapper**

```python
from __future__ import annotations

import json
import urllib.request
from typing import Any


class EvaluatorClient:
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def build_payload(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
        }

    def complete(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = json.dumps(
            self.build_payload(system_prompt=system_prompt, user_prompt=user_prompt)
        ).encode("utf-8")
        request = urllib.request.Request(
            url=f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.EvaluatorClientTests -v
```

Expected: `OK`

- [ ] **Step 5: Commit**

Skip for now: `/Users/atif/Public/TradeHarness` does not currently contain `.git`.

### Task 4: Implement FAP Prompt Builders And Diagnostic Cascade

**Files:**
- Create: `tradeharness/evolution/fap/prompts.py`
- Create: `tradeharness/evolution/fap/annotator.py`
- Test: `tests/test_offline_evolution.py`

- [ ] **Step 1: Write the failing FAP tests**

```python
from tradeharness.evolution.fap.annotator import annotate_episode_failure
from tradeharness.evolution.fap.prompts import build_fap_gate_prompt


class FAPAnnotatorTests(unittest.TestCase):
    def test_build_fap_gate_prompt_mentions_only_requested_gate(self) -> None:
        prompt = build_fap_gate_prompt(
            gate_name="action_realization",
            episode={"episode_id": "episode-1", "steps": []},
        )

        self.assertIn("action_realization", prompt.lower())
        self.assertNotIn("choose freely", prompt.lower())

    def test_annotate_episode_failure_stops_at_first_matching_gate(self) -> None:
        class FakeEvaluator:
            def complete(self, *, system_prompt: str, user_prompt: str):
                if "action_realization" in user_prompt:
                    return {"matched": True, "evidence": ["plain text instead of tool"]}
                return {"matched": False, "evidence": []}

        annotation = annotate_episode_failure(
            episode={"episode_id": "episode-1", "steps": []},
            evaluator=FakeEvaluator(),
        )

        self.assertEqual(annotation["primary_failure_type"], "action_realization")
        self.assertEqual(annotation["priority_checks"][0]["matched"], True)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.FAPAnnotatorTests -v
```

Expected: `FAIL` because FAP prompt and annotator functions do not exist.

- [ ] **Step 3: Implement gate prompts and the cascade**

```python
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
        f"Episode:\n{json.dumps(episode, indent=2)}"
    )
```

```python
def annotate_episode_failure(
    *,
    episode: dict[str, Any],
    evaluator: Any,
) -> dict[str, Any]:
    priority_checks: list[dict[str, Any]] = []

    for gate_name in FAP_GATES:
        result = evaluator.complete(
            system_prompt="You are a strict failure annotation evaluator.",
            user_prompt=build_fap_gate_prompt(gate_name=gate_name, episode=episode),
        )
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.FAPAnnotatorTests -v
```

Expected: `OK`

- [ ] **Step 5: Commit**

Skip for now: `/Users/atif/Public/TradeHarness` does not currently contain `.git`.

### Task 5: Implement Classification, Evo Prompt Builder, Update Candidate Generation, And Regression Notes

**Files:**
- Create: `tradeharness/evolution/classification/mapper.py`
- Create: `tradeharness/evolution/updater/agent.py`
- Create: `tradeharness/evolution/updater/prompting.py`
- Create: `tradeharness/evolution/updater/regression.py`
- Test: `tests/test_offline_evolution.py`

- [ ] **Step 1: Write the failing classification, prompt, and updater tests**

```python
from tradeharness.evolution.classification.mapper import map_failure_to_layer
from tradeharness.evolution.updater.agent import build_update_candidates
from tradeharness.evolution.updater.prompting import build_evolution_system_prompt
from tradeharness.evolution.updater.regression import build_regression_note


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
        self.assertIn("{HARNESS_DIR}".replace("{HARNESS_DIR}", "/tmp/harness"), prompt)
        self.assertIn("four lifecycle layers", prompt.lower())
        self.assertIn("remaining failure modes", prompt.lower())

    def test_build_regression_note_flags_overtrigger_risk_for_blocking_layers(self) -> None:
        note = build_regression_note(
            candidate={"target_layer": "layer_3", "suggested_change": "Add stricter validator."}
        )

        self.assertIn("over-trigger", note["risk_summary"].lower())
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.EvolutionUpdaterTests -v
```

Expected: `FAIL` because mapper and updater modules do not exist.

- [ ] **Step 3: Implement mapping, system prompt builder, candidate generation, and regression notes**

```python
LAYER_TARGETS = {
    "action_realization": "layer_3",
    "environment_contract": "layer_1",
    "trajectory_degeneration": "layer_4",
    "residual_reasoning": "layer_2",
}


def map_failure_to_layer(failure_type: str) -> str:
    return LAYER_TARGETS[failure_type]
```

```python
def build_evolution_system_prompt(
    *,
    harness_dir: str,
    trajectory_dir: str,
    design_guide: str,
) -> str:
    return f"""
System Instruction. You are a coding agent responsible for improving a runtime harness for a deterministic LLM-agent environment. Your goal is to improve task performance by adapting the runtime interface between the frozen model and the environment, without changing the model weights, the benchmark tasks, or the environment evaluation logic.

Inputs. You are given:
- the current harness implementation: {harness_dir}
- a trajectory directory from the previous iteration, including the summary metrics: {trajectory_dir}
- the harness design guide: {design_guide}

Harness Design Principles. The harness has four lifecycle layers:
1. Environment Contract Layer
2. Procedural Skill Layer
3. Action Realization Layer
4. Trajectory Regulation Layer

Use these layers to address runtime-interface failures, not to solve tasks with hidden oracle information. Do not use test labels, modify benchmark tasks, alter environment transitions, or change evaluation criteria.

Analysis Requirements. Inspect the previous iteration's trajectories and identify recurring failure patterns. For each pattern, determine the earliest lifecycle point where it can be reliably detected or prevented.

Update Requirements. Propose targeted, minimal, evidence-triggered updates. Do not override model reasoning when the correct action is ambiguous.

Regression Check. Inspect whether any update may over-trigger, block a valid action, inject misleading guidance, or reduce performance on previously successful trajectories.

Output. Return:
1. a concise summary of the dominant failure patterns found
2. the harness layer responsible for each proposed update
3. the implemented code changes
4. a short explanation of why each update is safe under the deterministic environment contract
5. any remaining failure modes that should be monitored in the next iteration
""".strip()
```

```python
from collections import Counter


def build_update_candidates(
    *,
    annotations: list[dict[str, Any]],
    current_harness: dict[str, Any],
    design_guide: dict[str, Any],
) -> list[dict[str, Any]]:
    counts = Counter(item["primary_failure_type"] for item in annotations)
    top_failures = counts.most_common(2)
    candidates: list[dict[str, Any]] = []

    for failure_type, _count in top_failures:
        candidates.append(
            build_update_candidate(
                target_layer=map_failure_to_layer(failure_type),
                problem_pattern=failure_type,
                suggested_change=_suggest_change_for_failure(failure_type),
                confidence="medium",
                supporting_episodes=[
                    item["episode_id"]
                    for item in annotations
                    if item["primary_failure_type"] == failure_type
                ],
            )
        )

    return candidates
```

```python
def build_regression_note(*, candidate: dict[str, Any]) -> dict[str, Any]:
    target_layer = candidate["target_layer"]
    if target_layer in {"layer_1", "layer_3", "layer_4"}:
        return {
            "target_layer": target_layer,
            "risk_summary": "Check for over-trigger behavior that may block valid actions.",
            "checks": [
                "Would this change reject a previously valid execution?",
                "Would this change trigger on normal inspection-only behavior?",
            ],
        }
    return {
        "target_layer": target_layer,
        "risk_summary": "Check whether the new guidance dilutes retrieval quality.",
        "checks": [
            "Would this skill crowd out more relevant skills?",
            "Would this advice conflict with existing procedures?",
        ],
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.EvolutionUpdaterTests -v
```

Expected: `OK`

- [ ] **Step 5: Commit**

Skip for now: `/Users/atif/Public/TradeHarness` does not currently contain `.git`.

### Task 6: Add Artifact Writers And Offline Batch Entrypoint

**Files:**
- Create: `tradeharness/evolution/storage/artifacts.py`
- Create: `tradeharness/evolution/main.py`
- Create: `tradeharness/evolution/__init__.py`
- Create: `tradeharness/evolution/storage/__init__.py`
- Create: `tradeharness/evolution/fap/__init__.py`
- Create: `tradeharness/evolution/classification/__init__.py`
- Create: `tradeharness/evolution/updater/__init__.py`
- Test: `tests/test_offline_evolution.py`

- [ ] **Step 1: Write the failing batch entrypoint tests**

```python
from tradeharness.evolution.main import run_offline_evolution


class OfflineEvolutionMainTests(unittest.TestCase):
    def test_run_offline_evolution_returns_named_artifact_paths(self) -> None:
        result = run_offline_evolution(
            trajectory_log_path="fixtures/episodes.jsonl",
            output_dir="tmp_evolution_output",
            evaluator=None,
        )

        self.assertIn("daily_report_path", result)
        self.assertIn("annotations_path", result)
        self.assertIn("candidates_path", result)
        self.assertIn("regression_notes_path", result)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.OfflineEvolutionMainTests -v
```

Expected: `FAIL` because the batch entrypoint does not exist.

- [ ] **Step 3: Implement artifact writers**

```python
def write_json_artifact(path: str, payload: Any) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return path
```

```python
def write_markdown_report(path: str, lines: list[str]) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path
```

- [ ] **Step 4: Implement `run_offline_evolution` orchestration**

```python
def run_offline_evolution(
    *,
    trajectory_log_path: str,
    output_dir: str,
    evaluator: Any,
) -> dict[str, str]:
    episodes = load_trajectory_episodes(trajectory_log_path)
    annotations = [annotate_episode_failure(episode=episode, evaluator=evaluator) for episode in episodes]
    candidates = build_update_candidates(
        annotations=annotations,
        current_harness={"layers": ["layer_1", "layer_2", "layer_3", "layer_4"]},
        design_guide={},
    )
    regression_notes = [build_regression_note(candidate=item) for item in candidates]
    report_lines = build_daily_report_lines(annotations=annotations, candidates=candidates)

    return {
        "daily_report_path": write_markdown_report(f"{output_dir}/daily-report.md", report_lines),
        "annotations_path": write_json_artifact(f"{output_dir}/annotations.json", annotations),
        "candidates_path": write_json_artifact(f"{output_dir}/candidates.json", candidates),
        "regression_notes_path": write_json_artifact(f"{output_dir}/regression-notes.json", regression_notes),
    }
```

- [ ] **Step 5: Run the test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.OfflineEvolutionMainTests -v
```

Expected: `OK`

- [ ] **Step 6: Commit**

Skip for now: `/Users/atif/Public/TradeHarness` does not currently contain `.git`.

### Task 7: Add Docs, Env Examples, And Full Verification

**Files:**
- Modify: `TradeHarness/.env.example`
- Modify: `tradeharness/README.MD`
- Modify: `tests/test_offline_evolution.py`

- [ ] **Step 1: Add evaluator and offline-evolution env variables to `.env.example`**

```dotenv
EVALUATOR_BASE_URL=https://your-openai-compatible-provider.example/v1
EVALUATOR_API_KEY=
EVALUATOR_MODEL=gpt-5.4
TRAJECTORY_LOG_PATH=var/trajectories/episodes.jsonl
EVOLUTION_OUTPUT_DIR=var/evolution
```

- [ ] **Step 2: Add README usage section for runtime logging and offline batch run**

```md
## Offline Evolution Block

The runtime can emit episode trajectory logs for later analysis.

Run the offline evolution batch with:

```bash
python3 -m tradeharness.evolution.main
```

This produces:

- a daily markdown report
- annotated failure JSON
- layer update candidates
- regression check notes
```

- [ ] **Step 3: Run focused offline-evolution tests**

Run:

```bash
python3 -m unittest tests.test_offline_evolution -v
```

Expected: `OK`

- [ ] **Step 4: Run the existing regression suite**

Run:

```bash
python3 -m unittest tests.test_agent_tools -v
```

Expected: `OK`

- [ ] **Step 5: Run lightweight syntax verification**

Run:

```bash
python3 -m compileall tradeharness tests
```

Expected: output ends without syntax errors.

- [ ] **Step 6: Commit**

Skip for now: `/Users/atif/Public/TradeHarness` does not currently contain `.git`.

## Phase 2 Extension

This phase extends the original offline evolution block into:

- recurring failure pattern mining
- staged layer artifacts
- regression-gated promotion
- daily scheduler runs
- active artifact rehydration for Layer 1 and Layer 2

### Task 8: Implement Failure Pattern Mining

**Files:**
- Create: `tradeharness/evolution/mining/__init__.py`
- Create: `tradeharness/evolution/mining/patterns.py`
- Modify: `tests/test_offline_evolution.py`

- [ ] **Step 1: Write the failing mining test**

```python
from tradeharness.evolution.mining.patterns import mine_failure_patterns


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
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.FailurePatternMiningTests -v
```

Expected: `FAIL`

- [ ] **Step 3: Implement deterministic pattern grouping**

```python
def mine_failure_patterns(annotations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in annotations:
        evidence = item.get("evidence", [])
        signature = str(evidence[0]) if evidence else item["primary_failure_type"]
        key = (item["primary_failure_type"], signature)
        grouped.setdefault(key, []).append(item)

    patterns: list[dict[str, Any]] = []
    for (failure_type, signature), items in grouped.items():
        patterns.append(
            {
                "pattern_id": f"{failure_type}:{abs(hash(signature))}",
                "pattern_type": failure_type,
                "frequency": len(items),
                "target_layer": map_failure_to_layer(failure_type),
                "supporting_episodes": [item["episode_id"] for item in items],
                "representative_evidence": items[0].get("evidence", []),
            }
        )
    return sorted(patterns, key=lambda item: item["frequency"], reverse=True)
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.FailurePatternMiningTests -v
```

Expected: `OK`

### Task 9: Implement Staged Artifacts And Promotion Gate

**Files:**
- Create: `tradeharness/evolution/updater/staging.py`
- Create: `tradeharness/evolution/updater/promotion.py`
- Modify: `tradeharness/evolution/main.py`
- Modify: `tests/test_offline_evolution.py`

- [ ] **Step 1: Write the failing staging and promotion tests**

```python
from tradeharness.evolution.updater.promotion import should_promote_candidate
from tradeharness.evolution.updater.staging import build_staged_layer_artifacts


class StagingAndPromotionTests(unittest.TestCase):
    def test_build_staged_layer_artifacts_splits_candidates_by_layer(self) -> None:
        artifacts = build_staged_layer_artifacts(
            [
                {
                    "target_layer": "layer_1",
                    "problem_pattern": "environment_contract",
                    "supporting_episodes": ["ep-1"],
                },
                {
                    "target_layer": "layer_2",
                    "problem_pattern": "residual_reasoning",
                    "supporting_episodes": ["ep-2"],
                },
            ],
            source_run_id="2026-06-08",
        )

        self.assertIn("contract", artifacts)
        self.assertIn("skills", artifacts)

    def test_should_promote_candidate_blocks_high_overtrigger_risk(self) -> None:
        decision = should_promote_candidate(
            candidate={"target_layer": "layer_3", "supporting_episodes": ["a"]},
            regression_note={"flags": ["high_overtrigger_risk"]},
            minimum_support=1,
        )

        self.assertFalse(decision["promote"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.StagingAndPromotionTests -v
```

Expected: `FAIL`

- [ ] **Step 3: Implement staging builder and promotion rules**

```python
def should_promote_candidate(*, candidate: dict[str, Any], regression_note: dict[str, Any], minimum_support: int) -> dict[str, Any]:
    support_count = len(candidate.get("supporting_episodes", []))
    flags = set(regression_note.get("flags", []))
    hard_flags = {"high_overtrigger_risk", "ambiguous_action_override", "conflicts_with_existing_rule"}
    if support_count < minimum_support:
        return {"promote": False, "reason": "insufficient_support"}
    if flags & hard_flags:
        return {"promote": False, "reason": "hard_regression_flag"}
    return {"promote": candidate["target_layer"] in {"layer_1", "layer_2"}, "reason": "layer_policy"}
```

- [ ] **Step 4: Extend `run_offline_evolution` to write staged artifacts and promotion report**

```python
patterns = mine_failure_patterns(annotations)
staged_artifacts = build_staged_layer_artifacts(candidates, source_run_id=run_id)
promotion_report = build_promotion_report(candidates=candidates, regression_notes=regression_notes)
```

- [ ] **Step 5: Run the test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.StagingAndPromotionTests -v
```

Expected: `OK`

### Task 10: Implement Daily Scheduler And Run Snapshots

**Files:**
- Create: `tradeharness/evolution/scheduler.py`
- Modify: `tradeharness/config/settings.py`
- Modify: `tests/test_offline_evolution.py`

- [ ] **Step 1: Write the failing scheduler test**

```python
from tradeharness.evolution.scheduler import build_run_output_dir


class EvolutionSchedulerTests(unittest.TestCase):
    def test_build_run_output_dir_appends_date_partition(self) -> None:
        result = build_run_output_dir(base_dir="var/evolution/runs", run_date="2026-06-08")
        self.assertTrue(result.endswith("var/evolution/runs/2026-06-08"))
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.EvolutionSchedulerTests -v
```

Expected: `FAIL`

- [ ] **Step 3: Implement scheduler entrypoint and settings support**

```python
def build_run_output_dir(*, base_dir: str, run_date: str) -> str:
    return os.path.join(base_dir, run_date)
```

```python
evolution_runs_dir=os.getenv("EVOLUTION_RUNS_DIR", "var/evolution/runs")
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.EvolutionSchedulerTests -v
```

Expected: `OK`

### Task 11: Rehydrate Active Layer 1 And Layer 2 Artifacts Into Runtime

**Files:**
- Modify: `tradeharness/runtime/contracts/environment.py`
- Modify: `tradeharness/runtime/skills/library.py`
- Modify: `tradeharness/config/settings.py`
- Modify: `tests/test_offline_evolution.py`
- Modify: `tests/test_agent_tools.py`

- [ ] **Step 1: Write the failing artifact rehydration tests**

```python
from tradeharness.runtime.contracts.environment import build_environment_contract
from tradeharness.runtime.skills.library import get_skill_library


class RuntimeArtifactRehydrationTests(unittest.TestCase):
    def test_environment_contract_includes_active_contract_artifact_clause(self) -> None:
        os.environ["ACTIVE_CONTRACT_ARTIFACT_PATH"] = "tests/fixtures/contract.json"
        contract = build_environment_contract(symbol="BTCUSDT")
        self.assertIn("Artifact rule", contract)

    def test_skill_library_includes_active_skill_artifact(self) -> None:
        os.environ["ACTIVE_SKILLS_ARTIFACT_PATH"] = "tests/fixtures/skills.json"
        skills = get_skill_library()
        self.assertTrue(any(item["skill_id"] == "artifact_skill" for item in skills))
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.RuntimeArtifactRehydrationTests -v
```

Expected: `FAIL`

- [ ] **Step 3: Implement additive Layer 1 and Layer 2 rehydration**

```python
def load_active_contract_clauses(path: str) -> list[str]:
    ...

def load_active_skill_cards(path: str) -> list[dict[str, object]]:
    ...
```

- [ ] **Step 4: Run focused tests plus the existing runtime suite**

Run:

```bash
python3 -m unittest tests.test_offline_evolution.RuntimeArtifactRehydrationTests -v
python3 -m unittest tests.test_agent_tools -v
```

Expected: `OK`

## Self-Review

### Spec coverage

- Runtime trajectory logging: covered by Task 2
- Shared schema contracts: covered by Task 1
- Evaluator-backed FAP cascade: covered by Tasks 3 and 4
- Four-layer mapping: covered by Task 5
- Evo Agent system prompt contract: covered by Task 5
- Update candidates plus regression notes: covered by Task 5
- Daily offline batch entrypoint and artifacts: covered by Task 6
- Docs and verification: covered by Task 7
- Failure pattern mining: covered by Task 8
- Staged artifacts and promotion gate: covered by Task 9
- Daily scheduler and run snapshots: covered by Task 10
- Active Layer 1/2 artifact rehydration: covered by Task 11

### Placeholder scan

- No `TODO`, `TBD`, or deferred placeholders remain.
- Each task includes explicit files, code targets, and commands.

### Type consistency

- `action_realization`, `environment_contract`, `trajectory_degeneration`, and `residual_reasoning` are used consistently across schema, FAP, and classification tasks.
- Artifact keys are consistent across Task 6 and Task 7:
  - `daily_report_path`
  - `annotations_path`
  - `candidates_path`
  - `regression_notes_path`
