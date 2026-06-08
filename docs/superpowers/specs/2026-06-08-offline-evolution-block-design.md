# Offline Evolution Block Design

## Goal

Add an `Offline Evolution Block` to `TradeHarness`.

This block is separate from the online trading runtime. It runs after daily demo or backtest activity and studies failed or weak agent trajectories to produce targeted harness updates.

Its role is to close the loop between:

- what the online agent did
- why it failed
- which LIFE-HARNESS layer should improve next

## Core Idea

The online runtime trades.

The offline evolution block learns from the runtime's trajectories and turns repeated failure patterns into better protection, guidance, and regulation for the next iteration of the harness.

This first version should include three connected stages:

1. `Failure Annotation Protocol (FAP)`
2. `Four-layer failure classification`
3. `Evolution updater`

Together they form one offline evolution workflow:

```text
Trajectory Logs
  -> FAP Diagnostic Cascade
  -> Four-Layer Classification
  -> Evolution Updater
  -> Regression Check
  -> Harness Update Artifacts
```

## Phase Boundary

This first version will:

- treat offline evolution as a dedicated subsystem outside the runtime loop
- read trajectory logs produced by the runtime
- use an external `OpenAI-compatible` evaluator API with model `gpt-5.4`
- diagnose failures using a priority-ordered FAP process
- map failures into the four LIFE-HARNESS layers
- produce structured harness-update artifacts instead of editing runtime code directly
- include regression-check notes for proposed updates

This first version will not:

- auto-commit code changes into the harness
- rewrite prompts or Python files automatically
- process multi-day portfolio analytics
- optimize model weights
- add queue-based distributed workers

## Architectural Boundary

The system should keep a clean boundary between online execution and offline evolution.

### Online Runtime Responsibilities

- run the Binance/LM Studio agent loop
- apply the four active harness layers during trading
- record trajectory logs for later analysis

### Offline Evolution Responsibilities

- read stored trajectory logs after the session or trading day
- run failure diagnosis
- identify the most important failure patterns
- recommend updates to the correct harness layers
- perform regression-oriented review notes on those updates

This separation keeps trading logic stable while letting the improvement loop evolve independently.

## Proposed Code Shape

This block should live outside `runtime/` because it is not part of the live trading loop.

```text
tradeharness/evolution/
  __init__.py
  main.py
  schemas.py
  fap/
    __init__.py
    annotator.py
    prompts.py
  classification/
    __init__.py
    mapper.py
  updater/
    __init__.py
    agent.py
    regression.py
  storage/
    __init__.py
    trajectories.py
    artifacts.py
```

The evaluator integration should be isolated from LM Studio:

```text
tradeharness/integrations/evaluator/
  __init__.py
  client.py
```

Responsibilities:

- `schemas.py`: shared data contracts for trajectories, annotations, and update candidates
- `storage/trajectories.py`: load and iterate trajectory logs
- `fap/annotator.py`: orchestrate the diagnostic cascade
- `fap/prompts.py`: build evaluator prompts for each diagnostic gate
- `classification/mapper.py`: map primary failures into the four LIFE-HARNESS layers
- `updater/agent.py`: generate targeted harness-update artifacts
- `updater/regression.py`: create regression-check notes and over-trigger warnings
- `integrations/evaluator/client.py`: call the third-party `OpenAI-compatible` evaluator API

## Trajectory Log Contract

The runtime should produce a structured `JSONL` trajectory log.

Each line should represent one complete episode so offline evolution can process episodes independently.

Each episode should contain:

- `episode_id`
- `started_at`
- `ended_at`
- `symbol`
- `mode`
- `final_status`
- `termination_reason`
- `steps`
- `final_outcome`

Each step should contain at least:

- `step_index`
- `observation`
- `decision_summary`
- `action`
- `harness_intervention`
- `environment_feedback`

### Step Semantics

- `observation`: raw environment information visible to the agent at that step
- `decision_summary`: an auditable reasoning summary, not raw hidden chain-of-thought
- `action`: the tool request or structured action the agent attempted
- `harness_intervention`: what Layer 3 or Layer 4 did with that action
- `environment_feedback`: the environment or harness result after the action attempt

This contract must be rich enough for diagnosis, but it should not depend on exposing hidden chain-of-thought internals.

## Failure Annotation Protocol

FAP is the first analysis stage.

Its job is to read one failed or weak trajectory and assign one primary failure label using a priority-ordered diagnostic cascade.

### Diagnostic Principle

FAP should follow a cascading priority rule:

- check outer technical failure first
- then business-rule failure
- then behavioral-trajectory failure
- finally residual reasoning failure

If a higher-priority category matches, FAP must stop and assign that label immediately.

### Ordered Failure Gates

1. `Action Realization`
2. `Environment Contract`
3. `Trajectory Degeneration`
4. `Residual Reasoning`

### Gate Questions

#### 1. Action Realization

Question:

`Did the agent actually express an executable action correctly?`

Typical evidence:

- plain text where a tool call was expected
- malformed structured action
- wrong tool name
- missing required action parameters

If matched:

- assign `action_realization`
- stop the cascade

#### 2. Environment Contract

Question:

`If the action was technically valid, did it violate the trading contract or operating procedure?`

Typical evidence:

- missing required protective parameters
- violating inspection-before-execution protocol
- using a correct parameter type with incorrect business meaning
- violating a known contract or action-gate rule

If matched:

- assign `environment_contract`
- stop the cascade

#### 3. Trajectory Degeneration

Question:

`If actions were individually valid, did the overall sequence become repetitive, stagnant, or budget-wasteful?`

Typical evidence:

- repeated blocked actions
- repeated inspect-only loops
- no convergence toward trade or no-trade conclusion
- budget exhaustion while still looping

If matched:

- assign `trajectory_degeneration`
- stop the cascade

#### 4. Residual Reasoning

Question:

`If the action format, contract compliance, and trajectory health were acceptable, did the agent still fail because its judgment was poor?`

Typical evidence:

- misreading market direction
- incorrect calculation
- weak tactical decision despite valid procedure

If reached:

- assign `residual_reasoning`

## FAP Execution Model

This repo should not implement FAP as a pure hard-coded if/else tree.

Instead, it should use a hybrid diagnostic architecture:

- the cascade order is controlled deterministically by code
- each diagnostic gate can use the evaluator model to assess whether the current failure type matches
- the evaluator must be instructed to answer only for the current gate, not to choose freely among all categories

This gives:

- deterministic priority behavior
- flexible interpretation of ambiguous cases
- traceable rationale output

## Annotation Output Contract

FAP should produce one structured annotation per episode.

Each annotation should include:

- `episode_id`
- `primary_failure_type`
- `failed_step_index`
- `priority_checks`
- `evidence`
- `rationale`

Example shape:

```json
{
  "episode_id": "trade_2026_06_08_001",
  "primary_failure_type": "environment_contract",
  "failed_step_index": 6,
  "priority_checks": [
    {"type": "action_realization", "matched": false},
    {"type": "environment_contract", "matched": true}
  ],
  "evidence": [
    "tool=open_long",
    "missing stop_loss",
    "layer3 decision=BLOCK"
  ],
  "rationale": "The action was technically well-formed but violated the trading contract requiring protection fields."
}
```

The first version should return exactly one primary failure type per episode.

## Four-Layer Classification

The classification stage should convert FAP output into a direct harness-target mapping.

The mapping is:

- `action_realization` -> `Layer 3`
- `environment_contract` -> `Layer 1`
- `trajectory_degeneration` -> `Layer 4`
- `residual_reasoning` -> `Layer 2`

This stage should remain explicit even though the mapping is simple.

Keeping it separate preserves a clean distinction between:

- diagnosis
- harness-target selection

That will make future changes easier if some failure types later map to multiple update paths.

## Evolution Updater

The evolution updater is the stage that turns annotated failures into proposed harness improvements.

It should be treated as a constrained coding or maintenance agent, not as an unconstrained auto-coder.

### Inputs

The updater should receive three inputs:

1. `Current Harness`
2. `Annotated Trajectories`
3. `Design Guide`

#### Current Harness

The current code, prompts, and rule text of the four active layers.

#### Annotated Trajectories

The trajectories already labeled by FAP and grouped into failure patterns.

#### Design Guide

The invariants for each layer.

Example:

- Layer 3 may block or canonicalize actions, but should not silently invent trading intent
- Layer 1 defines contract constraints and prompt-level rule text
- Layer 2 provides reusable procedural skills
- Layer 4 monitors whole-trajectory health

### Update Policy

The updater should not try to fix everything in one pass.

For each daily run it should:

- identify the most frequent or highest-risk failure patterns
- select only `1-2` top update targets
- generate targeted update artifacts for those targets

For this repo, safety-first priority should apply:

- prioritize `Layer 3` and `Layer 1`
- prefer code-based enforcement in `Layer 3` over prompt-only fixes when the issue is technical

### Targeted Update Mapping

#### Action Realization -> Layer 3

Suggested update types:

- validators
- canonicalizers
- stricter action parsing
- clearer block messages

Purpose:

- improve technical executability
- reduce malformed tool usage

#### Environment Contract -> Layer 1

Suggested update types:

- new contract clauses
- stronger tool descriptions
- stricter system-prompt operating rules

Purpose:

- reduce business-rule violations
- make safety constraints more explicit

#### Trajectory Degeneration -> Layer 4

Suggested update types:

- new monitors
- counters
- repetition heuristics
- stagnation triggers
- stronger budget-stop rules

Purpose:

- prevent wasteful loops
- stop unhealthy behavior earlier

#### Residual Reasoning -> Layer 2

Suggested update types:

- new skill cards
- improved procedural guidance
- better retrieval-facing strategy patterns

Purpose:

- improve practical decision quality without changing model weights

## Regression Check

Every proposed harness update must go through a regression-oriented review step.

The first version does not need full automated replay, but it must explicitly check for likely side effects such as:

- over-triggering
- blocking valid actions
- over-constraining normal trading flow
- degrading trajectories that previously succeeded

This should produce `regression check notes` alongside each update candidate.

The goal is to ensure the offline evolution loop does not harden the harness in a way that makes it brittle or unusable.

## Output Artifacts

The first version should write structured offline-evolution outputs, not source-code edits.

Required outputs:

- `daily evolution report`
- `annotated failures`
- `layer update candidates`
- `regression check notes`

These artifacts should be patch-ready enough that a later implementation phase can:

- review them manually
- promote them into code or prompt changes
- compare update quality across days

## Runtime Integration Boundary

The online runtime should only be extended enough to support the offline block.

The required runtime-side support is:

- emit structured trajectory episodes
- include step-level observation, decision summary, action, harness intervention, and environment feedback
- capture termination reason and final outcome

The runtime should not directly run offline evolution as part of the trading cycle.

## Entry Point

The offline block should expose a single batch entry point such as:

```text
python -m tradeharness.evolution.main
```

This command should:

1. load recent trajectory logs
2. run FAP over selected episodes
3. classify failures into the four layers
4. run the updater on the top patterns
5. emit offline-evolution artifacts

## Non-Goals

This design does not include:

- direct code mutation of harness files
- automatic git commits
- distributed job orchestration
- profit optimization logic beyond failure-driven improvement
- long-horizon portfolio risk analytics

## Why This Block Matters

The four online layers protect and guide the live agent, but they do not by themselves create a disciplined improvement loop.

The offline evolution block provides that loop.

It translates real failures into:

- clearer contracts
- stronger technical guards
- better procedural skills
- healthier trajectory regulation

That is how the harness becomes more robust over time without mixing unstable self-modification into the live runtime.

## Implementation Boundary

The next step is to write an implementation plan for:

- adding structured runtime trajectory logging
- defining shared evolution schemas
- implementing the evaluator-backed FAP cascade
- mapping annotations into harness layers
- generating targeted update artifacts with regression notes
- wiring a daily offline batch entry point
