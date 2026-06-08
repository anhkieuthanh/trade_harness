# Environment Contract Layer Design

## Goal

Add the first `Environment Contract Layer` to `TradeHarness` for the current `BTCUSDT Binance Futures` agent.

This layer is a prompt-augmentation and guardrail layer. It is not an execution-blocking validator in this phase.

Its purpose is to enrich the agent's operating contract so the LM Studio brain uses Binance tools with better sequencing, clearer assumptions, and fewer avoidable execution mistakes.

## Contract Model

The intended model is:

`C' = C ⊕ ΔC`

Where:

- `C` is the basic tool contract already exposed to the model
- `ΔC` is the environment-specific augmentation learned from practical execution needs

For this repo, `ΔC` will be specialized for:

- `BTCUSDT`
- `Binance Futures Testnet`
- the existing Binance toolset in `TradeHarness`

## Phase Boundary

This first version is limited to:

- prompt augmentation
- execution-safety guidance
- system-prompt injection
- tool-description injection

This first version does not:

- hard-block tool execution in code
- add full risk policy enforcement
- add market-news or slippage intelligence
- redesign trading strategy

## First Execution-Safety Focus

The first contract should teach the agent safe tool usage order before focusing on richer policy logic.

The contract should strongly reinforce:

- inspect market state before trading
- inspect current position before opening or closing
- inspect available balance before opening exposure
- avoid acting with incomplete state
- prefer observation tools before execution tools

## Contract Components For This Repo

### 1. Tool Clarification

Each Binance tool should explain:

- what it is for
- when it should be used
- what it does not imply

Examples for this repo:

- `get_market_snapshot` is the primary state-inspection tool for recent price and candles
- `get_position` must be checked before `open_long`, `open_short`, or `close_position`
- `get_balance` is used to confirm capital context before opening exposure
- `open_long` and `open_short` are execution tools, not discovery tools
- `close_position` should only be used when an open position exists

### 2. Policy Constraints

The first version should include only lightweight execution-safety policies, such as:

- do not open a position before inspecting market and position state
- do not call `close_position` unless position state has been checked
- do not assume flat state without checking `get_position`
- do not assume sizing safety without checking `get_balance`

These are still prompt-level constraints, not enforcement code.

### 3. Pitfall Warnings

The first version should encode simple, practical warnings for this repo:

- do not jump directly to execution tools without state inspection
- do not infer balance, position, or market state from previous turns alone
- do not treat a missing tool call as implicit approval to trade

This phase does not need external market-event logic yet.

### 4. Answer / Reasoning Format

Before requesting an execution tool, the agent should be nudged to summarize:

- what state it inspected
- why the chosen action follows from that state

This should remain lightweight and not become a verbose reporting protocol.

## Injection Points

The contract must be injected in two places:

### A. System Prompt

The runtime system prompt should include the environment contract so the agent sees the global rules of engagement for this market and tool environment.

This is where overall sequencing and safety expectations should live.

### B. Tool Descriptions

Each Binance tool definition should also carry concise contract language that clarifies:

- prerequisites
- intended use
- common misuse

This keeps the guardrails close to the individual tool surfaces.

## Proposed Code Shape

This layer should be implemented as its own runtime-facing module instead of embedding all contract text directly inside `runtime/agent.py`.

A suitable shape is:

```text
tradeharness/runtime/contracts/
  __init__.py
  environment.py
```

Responsibilities:

- build the environment contract text for the system prompt
- provide augmentation helpers for Binance tool descriptions
- keep contract wording centralized and editable

## Runtime Integration

The runtime should:

1. build the environment contract
2. merge it into the system prompt
3. request tool definitions that already include tool-level contract augmentation
4. continue using the existing agent loop behavior

This should be a behavior-preserving refactor plus prompt enrichment, not a runtime redesign.

## Non-Goals

This change should not:

- add new trading tools
- add execution blocking
- add stop-loss/take-profit enforcement
- add multi-symbol support
- add a generic cross-exchange contract framework yet

## Why This Layer Matters

Right now the agent can call tools, but the environment rules are still too implicit.

This layer makes those rules explicit in the same spirit as an operational contract:

- clarify tool semantics
- encode safety sequencing
- surface known execution pitfalls
- improve action quality without changing the core tool interface

## Implementation Boundary

The next step is to write a focused implementation plan for:

- adding the contract module
- injecting it into the runtime system prompt
- augmenting Binance tool descriptions
- verifying the dry-run agent still runs correctly
