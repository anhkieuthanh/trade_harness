# Action Realization Layer Design

## Goal

Add the third LIFE-HARNESS layer to `TradeHarness`: the `Action Realization Layer`.

For this repo, the first version will serve as a deterministic execution gatekeeper for the current `BTCUSDT Binance Futures` agent.

This layer should intervene after the LLM requests an action but before the tool is executed against Binance.

## Core Role

If:

- Layer 1 defines the rules
- Layer 2 provides procedural guidance

Then Layer 3 is the execution gatekeeper that enforces environment-valid actions in code.

Its job is not to advise. Its job is to decide whether an action is:

- `EXECUTE`
- `BLOCK`

based on deterministic environment evidence.

## Phase Boundary

This first version will:

- validate `state validity`
- return block feedback back into the agent loop
- allow the LLM to self-correct
- enforce a retry limit to avoid infinite correction loops

This first version will not:

- validate exchange-level quantity precision beyond existing tool behavior
- add full schema repair logic
- add market-news or latency-based feasibility rules
- redesign the trading strategy

## First Validation Scope

The first gatekeeper should enforce two state-aware rule groups:

### 1. Position-Aware Rules

- do not call `close_position` when the current position is `FLAT`
- do not call `open_long` when a position is already open
- do not call `open_short` when a position is already open

### 2. Inspection-Aware Rules

- do not allow execution tools unless the current loop has already inspected:
  - market snapshot
  - position state
  - balance state

In practice this means an entry action must not go through if the runtime has not gathered enough state evidence in the current cycle.

## Response Strategy

When the gatekeeper blocks an action:

- it must not execute the Binance tool
- it must return a structured block result
- the runtime must feed that block result back to the LLM so the model can attempt a corrected action

This first version should not terminate immediately on the first block unless the retry limit is reached.

## Retry Limit

To prevent infinite correction loops, the runtime must track how many blocked execution attempts occurred in the current cycle.

If the count exceeds a configured limit, the runtime should stop the cycle and return a final blocked summary rather than continuing indefinitely.

This limit should be small and deterministic.

A suitable first version is a constant such as:

- `MAX_ACTION_REALIZATION_RETRIES = 2`

or

- `MAX_ACTION_REALIZATION_RETRIES = 3`

The exact constant can be chosen during implementation, but it must be explicit in code.

## Proposed Code Shape

This layer should live beside the other runtime-owned orchestration layers:

```text
tradeharness/runtime/action_realization/
  __init__.py
  gate.py
```

Responsibilities:

- inspect requested execution actions
- read deterministic state evidence
- return `EXECUTE` or `BLOCK`
- provide block reasons in a format the runtime can pass back to the LLM

This first version does not require a separate models file unless the result object becomes too large.

## Gate Input

The gatekeeper should evaluate at least:

- requested tool name
- requested arguments
- current position state
- whether market snapshot was inspected in the current cycle
- whether position was inspected in the current cycle
- whether balance was inspected in the current cycle

The important principle is that the gate decision must depend on deterministic runtime state, not on prompt interpretation.

## Gate Output

The gate should return a simple structured result that the runtime can branch on.

A suitable output shape is:

```text
{
  "decision": "EXECUTE" | "BLOCK",
  "reason": "...",
  "details": {...}
}
```

When blocked, the reason should be clear enough for the LLM to revise its next action.

## Runtime Integration

The runtime should:

1. receive a tool request from the LLM
2. detect whether it is an execution tool
3. call the action-realization gate before executing it
4. if `EXECUTE`, continue to `toolset.run_tool(...)`
5. if `BLOCK`, append the block feedback into the conversation and let the model try again
6. stop if the retry limit is exceeded

Observation tools such as:

- `get_market_snapshot`
- `get_position`
- `get_balance`

should not be blocked by this layer in the first version.

## Non-Goals

This change should not:

- add new trading tools
- add hard market-risk policy logic
- add quantity rounding enforcement beyond existing tool behavior
- replace Layer 1 or Layer 2 logic
- introduce generic multi-exchange action realization yet

## Why This Layer Matters

Right now the system can prompt the model with rules and skills, but those are still advisory.

Layer 3 is the first layer that turns those expectations into deterministic runtime enforcement.

That is important because:

- the model can still misunderstand context
- the model can still attempt invalid execution
- prompt guidance alone is not enough for reliable live behavior

## Implementation Boundary

The next step is to write an implementation plan for:

- adding the action-realization gate module
- wiring it into the runtime loop
- enforcing position-aware and inspection-aware blocking
- returning block feedback to the LLM
- enforcing a retry limit
- verifying the dry-run agent still behaves correctly
