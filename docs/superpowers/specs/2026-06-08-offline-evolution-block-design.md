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

This first version should include five connected stages:

1. `Failure Annotation Protocol (FAP)`
2. `Four-layer failure classification`
3. `Failure pattern mining`
4. `Evolution updater`
5. `Regression-gated promotion`

Together they form one offline evolution workflow:

```text
Trajectory Logs
  -> FAP Diagnostic Cascade
  -> Four-Layer Classification
  -> Failure Pattern Mining
  -> Evolution Updater
  -> Regression Check
  -> Staged Harness Updates
  -> Promotion Gate
  -> Harness t+1 Artifacts
```

## Phase Boundary

This first version will:

- treat offline evolution as a dedicated subsystem outside the runtime loop
- read trajectory logs produced by the runtime
- use an external `OpenAI-compatible` evaluator API with model `gpt-5.4`
- diagnose failures using a priority-ordered FAP process
- map failures into the four LIFE-HARNESS layers
- mine recurring failure patterns across annotated trajectories
- write staged harness updates before promotion
- include regression-check notes for proposed updates
- support promotion from `staging` to `current` only after regression checks pass

This first version will not:

- auto-commit code changes into the harness
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
- identify recurring failure patterns
- select the earliest and cheapest viable harness layer for each pattern
- write staged updates for the selected layer
- perform regression-oriented review notes on those staged updates
- promote only safe staged updates into active harness artifacts

This separation keeps trading logic stable while letting the improvement loop evolve independently.

## Proposed Code Shape

This block should live outside `runtime/` because it is not part of the live trading loop.

```text
tradeharness/evolution/
  __init__.py
  main.py
  schemas.py
  scheduler.py
  fap/
    __init__.py
    annotator.py
    prompts.py
  classification/
    __init__.py
    mapper.py
  mining/
    __init__.py
    patterns.py
  updater/
    __init__.py
    agent.py
    staging.py
    promotion.py
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
- `mining/patterns.py`: group repeated annotations into recurring failure patterns
- `updater/agent.py`: decide the most local and effective harness fix for each pattern
- `updater/staging.py`: write staged layer-specific updates
- `updater/regression.py`: create regression-check notes and over-trigger warnings
- `updater/promotion.py`: decide whether staged artifacts can become active
- `scheduler.py`: run the daily offline evolution batch and promotion flow
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

## Failure Pattern Mining

The system should not update the harness based on isolated single-episode failures alone.

After annotation and classification, it should group repeated failures into recurring patterns.

### Purpose

Pattern mining exists to answer:

- what failure mode repeats often enough to justify a harness change
- which failures are merely noise
- which layer should be updated first for maximum effect and minimum intervention

### Mining Rules

The first version should group failures using deterministic pattern keys built from fields such as:

- `primary_failure_type`
- tool name
- repeated block reason
- missing or malformed argument signature
- repeated trajectory stagnation signature

Examples:

- repeated misuse of `get_balance` with symbol-like assets
- repeated missing required protective fields
- repeated inspect-only loops
- repeated same blocked action with same reason

### Mining Output

Each mined pattern should include:

- `pattern_id`
- `pattern_type`
- `frequency`
- `target_layer`
- `supporting_episodes`
- `representative_evidence`

This pattern record becomes the unit of work for the evolution updater.

## Evolution Updater

The evolution updater is the stage that turns annotated failures into proposed harness improvements.

It should be treated as a constrained coding or maintenance agent, not as an unconstrained auto-coder.

### Evo Agent System Prompt Contract

The evolution updater should be driven by a stable system instruction.

This instruction should frame the updater as a coding agent that improves the runtime harness, not the underlying model, task set, or evaluator.

The prompt contract should contain the following sections.

#### System Instruction

The agent is responsible for improving a runtime harness for a deterministic LLM-agent environment.

Its goal is to improve task performance by adapting the runtime interface between the frozen model and the environment, without changing:

- model weights
- benchmark tasks
- environment evaluation logic

#### Inputs

The prompt should explicitly mention three inputs:

- `Current Harness`: `{HARNESS_DIR}`
- `Trajectory Directory`: `{TRAJECTORY_DIR}`
- `Design Guide`: `{DESIGN_GUIDE}`

The model may receive these either inline or through referenced content, but the prompt must name them explicitly.

#### Harness Design Principles

The prompt should restate the four lifecycle layers:

1. `Environment Contract Layer`
2. `Procedural Skill Layer`
3. `Action Realization Layer`
4. `Trajectory Regulation Layer`

It should also state the critical guardrail:

- use these layers to address runtime-interface failures
- do not solve tasks with hidden oracle information
- do not use test labels
- do not modify benchmark tasks
- do not alter environment transitions
- do not change evaluation criteria

#### Analysis Requirements

The prompt should instruct the agent to:

- inspect previous trajectories
- identify recurring failure patterns
- locate the earliest lifecycle point where each pattern can be reliably detected or prevented

The allowed lifecycle insertion points are:

- before interaction, via contract clarification
- during task conditioning, via skill retrieval
- before environment execution, via validation or canonicalization
- after execution, via trajectory monitoring and recovery

The prompt should emphasize deterministic and mechanically identifiable failure types such as:

- invalid action formats
- wrong tool conventions
- missing required fields
- repeated noop actions
- loops
- premature submissions
- budget exhaustion
- recurring procedural mistakes

#### Update Requirements

The prompt should instruct the agent to propose and implement targeted updates that are:

- evidence-triggered
- local and minimal
- non-oracular
- evaluation-preserving
- robust to unseen tasks from the same environment

The prompt should explicitly prohibit overriding model reasoning when the correct action is ambiguous.

#### Regression Check

The prompt should require the updater to inspect whether a proposed change may:

- over-trigger
- block valid actions
- inject misleading guidance
- reduce performance on previously successful trajectories

If negative side effects are found, the updater must revise the proposal.

#### Output Requirements

The prompt should require five output sections:

1. dominant failure patterns found
2. responsible harness layer for each update
3. implemented code changes
4. safety explanation under the deterministic environment contract
5. remaining failure modes to monitor next

This output contract should shape both human-readable reports and machine-usable updater artifacts.

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

### Four-Step Update Loop

The updater should follow a fixed four-step logic:

1. `Failure Pattern Mining`
2. `Layer Mapping`
3. `Implementation`
4. `Regression Check`

This keeps update behavior disciplined and auditable.

### Layer Mapping Principle

For each recurring failure pattern, the updater should choose the earliest lifecycle point where the failure can be detected or prevented cheaply and reliably.

Priority:

- fix with `Layer 3` if a deterministic validator or canonicalizer can solve it
- otherwise fix with `Layer 1` if the issue is a stable contract or policy mismatch
- use `Layer 4` for repeated post-execution degeneration patterns
- use `Layer 2` when the issue is procedural weakness rather than deterministic invalidity

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

## Staged Implementation

The first version should allow the coding agent to write staged harness updates before they become active.

That means update generation is no longer limited to passive reports.

### Staging Principle

The coding agent may write into a staging area, but it must not modify the active harness directly.

The flow is:

```text
Mined Pattern
  -> Layer Mapping
  -> Staged Update Write
  -> Regression Check
  -> Promotion Gate
  -> Active Harness Artifact
```

### Update Forms By Layer

#### Layer 1

Write staged contract artifacts such as:

- additional contract clauses
- stronger tool-specific warnings
- extra stable policy text

#### Layer 2

Write staged skill artifacts such as:

- new skill cards
- new anti-pattern guidance
- new procedural sequences

#### Layer 3

Write staged action artifacts such as:

- validator rules
- canonicalization rules
- block-message improvements

#### Layer 4

Write staged trajectory artifacts such as:

- monitor rules
- counters
- repetition thresholds
- recovery triggers

### Update Requirements

Every staged update must satisfy:

- `precise triggering`: it activates only on clear trajectory or environment evidence
- `minimality`: it is the smallest local change that addresses the failure
- `non-overreach`: it does not override the model when the correct action remains ambiguous

## Regression Check

Every proposed harness update must go through a regression-oriented review step.

The first version does not need full automated replay, but it must explicitly check for likely side effects such as:

- over-triggering
- blocking valid actions
- over-constraining normal trading flow
- degrading trajectories that previously succeeded

This should produce `regression check notes` alongside each update candidate.

The goal is to ensure the offline evolution loop does not harden the harness in a way that makes it brittle or unusable.

## Scheduler And Promotion Flow

The repo should support a daily batch scheduler for offline evolution.

### Scheduler Model

The first version should use a batch entry point, not a long-running daemon.

Recommended command:

```text
python -m tradeharness.evolution.scheduler
```

This job should:

1. load recent trajectory logs
2. run annotation and pattern mining
3. write staged updates
4. run regression checks
5. decide promotion
6. persist the run snapshot

External scheduling may be handled by `cron` or `launchd`.

### Artifact Layout

The first version should separate:

- dated run outputs
- staged updates
- current active updates

Recommended structure:

```text
var/evolution/runs/YYYY-MM-DD/
tradeharness/evolution/artifacts/staging/
tradeharness/evolution/artifacts/current/
```

### Layer Artifact Schema

The active and staged artifact directories should contain layer-specific files such as:

- `contract.json`
- `skills.json`
- `action_rules.json`
- `trajectory_rules.json`

#### `contract.json`

- `version`
- `generated_at`
- `source_run_id`
- `clauses`

Each clause should contain:

- `id`
- `priority`
- `rule_text`
- `trigger_pattern`
- `supporting_episodes`

#### `skills.json`

- `version`
- `generated_at`
- `source_run_id`
- `skills`

Each skill should contain:

- `skill_id`
- `title`
- `tags`
- `when_to_use`
- `procedure`
- `anti_patterns`
- `source_episodes`

#### `action_rules.json`

- `version`
- `generated_at`
- `source_run_id`
- `rules`

Each rule should contain:

- `rule_id`
- `tool_name`
- `condition`
- `decision`
- `message`
- `supporting_episodes`

#### `trajectory_rules.json`

- `version`
- `generated_at`
- `source_run_id`
- `rules`

Each rule should contain:

- `rule_id`
- `pattern_type`
- `window`
- `threshold`
- `decision`
- `message`
- `supporting_episodes`

## Promotion Gate

Staged updates should not become active automatically unless they pass a minimal promotion gate.

### Promotion Conditions

A staged artifact may be promoted only if:

1. it meets the evidence threshold
2. it has no hard regression warning
3. it is additive rather than destructive

### Evidence Threshold

Each candidate should have at least `N` supporting episodes.

The first version may default to `N = 1`, but the threshold should be configurable.

### Hard Regression Warnings

Any staged update should fail promotion if regression notes indicate risks such as:

- `high_overtrigger_risk`
- `ambiguous_action_override`
- `conflicts_with_existing_rule`

### Layer-Safe Promotion

The first version should auto-promote only additive updates.

Recommended policy:

- `Layer 1`: may auto-promote
- `Layer 2`: may auto-promote
- `Layer 3`: manual or stricter promotion only
- `Layer 4`: manual or stricter promotion only

This balances learning speed with runtime safety.

## Output Artifacts

The first version should write structured offline-evolution outputs, not source-code edits.

Required outputs:

- `daily evolution report`
- `annotated failures`
- `mined failure patterns`
- `layer update candidates`
- `staged layer artifacts`
- `regression check notes`
- `promotion report`

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
- read active additive harness artifacts on startup or per cycle

The first version should only rehydrate additive artifacts from the `current` directory.

That means:

- Layer 1 appends active contract clauses
- Layer 2 merges active skill cards
- Layer 3 may later read active additive rule records
- Layer 4 may later read active additive monitor records

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
4. mine recurring failure patterns
5. run the updater on the top patterns
6. write staged artifacts
7. emit offline-evolution artifacts

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
- mining recurring failure patterns
- generating staged updates with regression notes
- wiring a daily offline batch scheduler
- defining promotion and active-artifact rehydration flow
