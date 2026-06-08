# Trajectory Regulation Layer Design

## Goal

Add the fourth LIFE-HARNESS layer to `TradeHarness`: the `Trajectory Regulation Layer`.

For this repo, the first version will supervise the agent's multi-step behavior across the whole runtime cycle and intervene when the trajectory shows signs of degeneration.

This layer is higher-level than Action Realization. It does not only ask whether one action is valid. It asks whether the overall sequence of behavior is still healthy and progressing toward a useful outcome.

## Core Role

If:

- Layer 1 defines the rules
- Layer 2 supplies procedural experience
- Layer 3 blocks invalid execution actions

Then Layer 4 monitors whether the overall trajectory is still productive, or whether the agent is getting stuck, repetitive, or wasteful.

Its job is to return one of three outcomes:

- `ALLOW`
- `WARN`
- `STOP`

based on the recent interaction trajectory.

## Phase Boundary

This first version will:

- regulate repetition
- regulate stagnation
- regulate budget exhaustion
- issue soft warnings or hard stops
- monitor both tool-level and turn-level signals

This first version will not:

- perform market-PnL-based revenge-trading detection yet
- monitor long-term multi-session behavior
- add an external analytics store
- redesign the overall runtime loop

## Monitoring Strategy

This first version should use a hybrid strategy:

- tool-level monitoring for:
  - repetition
  - stagnation
- turn-level monitoring for:
  - budget exhaustion

That gives enough visibility without making the runtime excessively complicated in the first implementation.

## First Degeneration Types

### 1. Repetition

Examples for this repo:

- repeating the same observation tool too many times without changing direction
- repeating the same blocked action with the same reason
- looping through equivalent requests without progressing toward a final answer

The first version should detect simple repeated patterns using recent history and counters.

### 2. Stagnation

Examples for this repo:

- different actions are being taken, but no meaningful state or decision progress occurs
- the agent keeps inspecting but never gets closer to a trade or explicit no-trade conclusion
- the tool path churns without a meaningful change in outcome

The first version does not need deep semantic progress modeling. A practical heuristic based on repeated non-progress signals is enough.

### 3. Budget Exhaustion

Examples for this repo:

- only a small number of loop steps remain
- the agent still has not produced a final answer
- it keeps inspecting or correcting instead of concluding

This should trigger increasingly strong intervention as the cycle budget becomes tight.

## Intervention Model

The first version should support two levels of intervention:

### `WARN`

A soft guidance message appended back into the conversation.

Purpose:

- draw the agent's attention to repetition, stagnation, or remaining budget
- nudge it to change behavior
- preserve autonomy when recovery is still likely

### `STOP`

A hard termination of the current cycle with a forced final summary.

Purpose:

- prevent wasteful or unhealthy looping
- stop clearly degenerate trajectories
- preserve runtime budget and reduce unsafe over-processing

## Proposed Code Shape

This layer should live under runtime because it supervises runtime behavior:

```text
tradeharness/runtime/trajectory_regulation/
  __init__.py
  monitor.py
```

This first version does not require a separate history file unless the state structure becomes too large.

## Minimum Tracked History

The monitor should have access to a compact trajectory history for the current cycle, including:

- tool names requested
- whether a tool call was blocked
- block reasons
- simplified tool result categories
- loop step index
- remaining budget
- whether a final answer has already been produced

This does not need full transcript replay in the first version.

## Regulation Heuristics

The first version should use deterministic heuristics such as:

### Repetition heuristics

- same tool requested more than `N` times in a short window
- same block reason repeated more than `N` times

### Stagnation heuristics

- too many observation-only steps without progressing to a final answer
- repeated cycles of inspection with no meaningful change in direction

### Budget heuristics

- remaining steps fall below a threshold and no final answer exists
- repeated warnings near the end of the budget escalate to stop

The exact thresholds can be finalized during implementation, but they must be explicit in code.

## Runtime Integration

The runtime should:

1. append tool-level events into a compact trajectory history
2. call the regulator after meaningful tool-level updates
3. call the regulator again at turn boundaries to assess budget exhaustion
4. if result is `ALLOW`, continue normally
5. if result is `WARN`, append a warning message to the conversation
6. if result is `STOP`, terminate the cycle with a forced final summary

## Non-Goals

This change should not:

- replace Action Realization checks
- add execution blocking based on market profitability
- persist trajectory history across sessions
- introduce probabilistic or ML-based trajectory scoring

## Why This Layer Matters

Even if each individual action is technically valid, an agent can still degrade over time:

- repeat unhelpful actions
- stall without converging
- burn budget without reaching a conclusion

Layer 4 exists to detect and regulate that broader behavioral failure mode.

It is the first layer that supervises the health of the whole decision path, not just its local correctness.

## Implementation Boundary

The next step is to write an implementation plan for:

- adding the trajectory monitor
- defining trajectory history shape
- adding repetition, stagnation, and budget heuristics
- wiring `ALLOW/WARN/STOP` into the runtime loop
- verifying the dry-run agent still behaves correctly
