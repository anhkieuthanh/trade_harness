# Agent Architecture Folder Refactor Design

## Goal

Reorganize `TradeHarness` so the code structure matches the intended agent architecture:

- `LM Studio` is the brain
- `Binance` is exposed through tools
- `runtime` only orchestrates the agent loop

The current flat package layout works for the MVP, but it mixes architectural responsibilities and will become harder to extend once more exchanges, tools, or strategies are added.

## Desired Folder Structure

The refactor should move the package toward this shape:

```text
tradeharness/
  config/
    __init__.py
    settings.py
  domain/
    __init__.py
    models.py
  integrations/
    __init__.py
    binance/
      __init__.py
      client.py
    lmstudio/
      __init__.py
      client.py
  runtime/
    __init__.py
    agent.py
    main.py
  tools/
    __init__.py
    binance.py
```

## Architecture Boundaries

### `config`

Responsible only for loading and validating runtime settings from `.env` and environment variables.

It should not know anything about Binance tool behavior or agent orchestration.

### `domain`

Responsible for shared data contracts:

- candles
- positions
- symbol filters
- tool requests

These models should stay free of network and orchestration concerns.

### `integrations/binance`

Responsible only for low-level Binance Futures Testnet communication:

- request signing
- market/account/execution REST calls
- translating raw Binance payloads into domain models where appropriate

This layer should not decide whether the agent should open or close positions.

### `integrations/lmstudio`

Responsible only for talking to the OpenAI-compatible LM Studio endpoint:

- sending messages
- passing tool definitions
- reading assistant message content
- extracting tool requests from either native `tool_calls` or JSON fallback format

This refactor explicitly moves the old `decision_engine.py` responsibility into this integration layer.

The agent no longer revolves around a fixed `BUY | SELL | HOLD | CLOSE` decision parser. Instead, the model decides which tool to call.

### `tools`

Responsible for business-level tool behavior exposed to the LLM:

- `get_market_snapshot`
- `get_balance`
- `get_position`
- `open_long`
- `open_short`
- `close_position`

This is the translation layer between agent-intent and exchange-client operations.

### `runtime`

Responsible only for orchestration:

- build the initial message set
- pass tool definitions to LM Studio
- execute requested tools
- append tool results back into the conversation
- stop once the agent returns a final answer or the step limit is reached

This layer should not contain Binance request code or LLM response parsing internals.

## File Mapping From Current Layout

The current files should map approximately as follows:

- `tradeharness/config.py` -> `tradeharness/config/settings.py`
- `tradeharness/models.py` -> `tradeharness/domain/models.py`
- `tradeharness/binance_client.py` -> `tradeharness/integrations/binance/client.py`
- `tradeharness/llm_client.py` -> `tradeharness/integrations/lmstudio/client.py`
- `tradeharness/binance_tools.py` -> `tradeharness/tools/binance.py`
- `tradeharness/agent_runtime.py` -> `tradeharness/runtime/agent.py`
- `tradeharness/main.py` -> `tradeharness/runtime/main.py`

`tradeharness/decision_engine.py` should be removed after its remaining responsibilities are absorbed into the LM Studio integration layer.

## Import and Compatibility Strategy

This should be a structural refactor, not a behavior rewrite.

The implementation should:

- keep the current runtime behavior intact
- update imports cleanly across the package
- keep the top-level `python3 -m tradeharness.main` run path working, either through a thin compatibility wrapper or by updating the package entrypoint cleanly

## Verification Expectations

The refactor should preserve:

- existing unit tests for tool extraction and Binance tool dispatch
- successful Python compile checks
- the current dry-run agent loop behavior

## Non-Goals

This refactor does not need to:

- add new trading features
- add new tools
- add strategy logic
- add a new exchange
- redesign the prompt behavior beyond what is required for the file move

## Why This Structure

This layout matches the mental model you described:

- `brain` lives under LM Studio integration
- `tools` are explicit and discoverable
- `runtime` becomes a clean orchestrator
- exchange communication becomes swappable

That makes later work easier:

- add Bybit under `integrations/bybit/`
- add new tool groups under `tools/`
- add strategy or policy modules without polluting transport code

## Implementation Boundary

The next step is to write a focused implementation plan for moving files, updating imports, preserving compatibility, and re-running the current verification flow.
