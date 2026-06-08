# TradeHarness

Minimal local agent bridge between LM Studio and Binance Futures Testnet for `BTCUSDT`.

## Package Layout

- `tradeharness/config/`: runtime settings
- `tradeharness/domain/`: shared data contracts
- `tradeharness/integrations/binance/`: low-level Binance client
- `tradeharness/integrations/lmstudio/`: LM Studio client and tool-request parsing
- `tradeharness/tools/`: Binance tools exposed to the agent
- `tradeharness/runtime/`: agent orchestration loop

## Environment Contract Layer

The runtime includes a prompt-augmentation contract layer specialized for:

- `BTCUSDT`
- `Binance Futures Testnet`
- the current Binance toolset

This layer injects execution-safety guidance into:

- the runtime system prompt
- each Binance tool description

It is a guardrail and prompt-enrichment layer only in the current phase. It does not hard-block execution in code.

## Procedural Skill Layer

The runtime also includes a procedural skill layer for entry execution.

- skills are stored locally in the repo
- retrieval uses BM25 scoring in-memory
- the retrieval query is built from user task, market snapshot, position state, and tool intent
- selected skills are injected into the prompt under a `Relevant Skills` block

This phase focuses only on entry-execution guidance and does not yet include automatic skill distillation or execution blocking.

## Action Realization Layer

The runtime includes a deterministic action-realization gate for execution tools.

- it checks state validity before execution tools are allowed through
- it blocks invalid entry or close actions before they reach Binance
- it feeds block feedback back to the LLM so the model can self-correct
- it enforces a small retry limit to prevent infinite correction loops

This first phase validates position-aware and inspection-aware state only.

## Trajectory Regulation Layer

The runtime includes a trajectory-regulation layer that supervises the health of the full agent loop.

- it monitors repetition, stagnation, and budget exhaustion
- it can issue soft warnings back to the LLM
- it can hard-stop the cycle when the trajectory becomes too unhealthy
- it uses compact per-cycle history rather than a cross-session store

This first phase is deterministic and local to the current runtime cycle.

## What It Does

- uses LM Studio as the agent brain
- exposes Binance market/account/execution operations as tools
- lets the agent inspect state before deciding to trade
- optionally places a demo futures order

## Setup

```bash
cd /Users/atif/Public/TradeHarness
python3 -m pip install -r requirements.txt
cp .env.example .env
```

Fill in:

- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`

LM Studio defaults:

- URL: `http://192.168.10.17:1234/v1`
- Model: `google/gemma-4-e2b`

## Run

Dry run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m tradeharness.main
```

Real demo order mode:

Set `DRY_RUN=false` in `.env`, then run the same command.

## Agent Model

- Brain: LM Studio `google/gemma-4-e2b`
- Tools:
  - `get_market_snapshot`
  - `get_balance`
  - `get_position`
  - `open_long`
  - `open_short`
  - `close_position`

The runtime supports both native OpenAI-compatible `tool_calls` and a JSON fallback tool request format for local models that do not emit structured tool calls reliably.
