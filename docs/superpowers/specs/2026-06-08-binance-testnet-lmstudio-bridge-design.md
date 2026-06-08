# Binance Testnet LM Studio Bridge Design

## Goal

Create a minimal local flow that lets an LLM running in LM Studio decide whether to trade the `BTCUSDT` Binance Futures Testnet pair.

The current goal is only to connect:

- local LLM at `http://192.168.10.17:1234/v1`
- model `google/gemma-4-e2b`
- Binance Futures Testnet market data and order execution

This phase does not include advanced error handling, observability, dashboards, or formal test coverage.

## Scope

The first version will:

- run as a local Python polling worker
- fetch the current BTC futures price and a small set of recent candles
- send that context to the LLM through LM Studio's OpenAI-compatible API
- require the model to return one action from `BUY`, `SELL`, `HOLD`, or `CLOSE`
- translate that action into a Binance Futures Testnet API call
- size new positions as a percentage of available demo USDT balance

The first version will not:

- manage take-profit or stop-loss orders
- expose an HTTP API
- support multiple symbols
- support multiple exchanges
- include rich logging, retry policies, or analytics

## Runtime Flow

Each polling cycle follows this sequence:

1. Read config from environment.
2. Fetch account balance, current BTCUSDT price, and recent candles from Binance Futures Testnet.
3. Build a compact prompt for the LLM.
4. Call LM Studio at `/v1/chat/completions` using model `google/gemma-4-e2b`.
5. Parse the returned action.
6. Inspect the current futures position.
7. Map the action to a Binance Futures Testnet order:
   - `BUY`: open a long position if no position is open
   - `SELL`: open a short position if no position is open
   - `HOLD`: do nothing
   - `CLOSE`: close the current open position if one exists
8. Sleep until the next polling interval.

## Components

### `config`

Loads required environment variables:

- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`
- `LMSTUDIO_BASE_URL`
- `LMSTUDIO_MODEL`
- `SYMBOL`
- `POLL_INTERVAL_SECONDS`
- `CANDLE_INTERVAL`
- `CANDLE_LIMIT`
- `TRADE_SIZE_PERCENT`
- `DRY_RUN`

Defaults should make local startup simple:

- `LMSTUDIO_BASE_URL=http://192.168.10.17:1234/v1`
- `LMSTUDIO_MODEL=google/gemma-4-e2b`
- `SYMBOL=BTCUSDT`

### `binance_client`

Provides the minimum Binance Futures Testnet integration needed to:

- fetch ticker price
- fetch recent klines
- fetch available USDT balance
- fetch current symbol position
- place a market order
- close an existing position
- fetch exchange info needed for quantity rounding

### `llm_client`

Calls the LM Studio OpenAI-compatible endpoint and returns the raw model response.

The prompt contract must instruct the model to return a strict JSON object with:

- `action`
- `reason`

`action` must be one of `BUY`, `SELL`, `HOLD`, or `CLOSE`.

### `decision_engine`

Builds the prompt from:

- current symbol
- latest price
- recent candles
- current position state

It then parses the model output into a normalized decision object.

### `trader`

Converts the decision into exchange actions.

Rules:

- `BUY` only opens a long if there is no current position
- `SELL` only opens a short if there is no current position
- `CLOSE` only closes if there is an open position
- new order quantity is calculated from `TRADE_SIZE_PERCENT` and current BTC price
- quantity is rounded to Binance symbol filters before submission

### `main`

Runs the polling loop and coordinates all modules.

## Data Contract Between LLM and Worker

The worker sends a compact prompt and expects a strict JSON response like:

```json
{
  "action": "BUY",
  "reason": "Short-term candles suggest upward momentum."
}
```

Only `action` is required for execution. `reason` is included for operator visibility.

## Safety Boundaries For This Phase

This phase stays intentionally narrow:

- trading is limited to Binance Futures Testnet
- trading is limited to `BTCUSDT`
- only one simple polling worker runs locally
- only market open and market close actions are supported
- no pyramiding or reversing in the same cycle

## Deliverables

Implementation should produce:

- a runnable Python project in `TradeHarness`
- an `.env.example` file for local setup
- a short `README.MD` explaining setup and run commands
- a polling worker that can call LM Studio and submit demo futures orders to Binance Futures Testnet

## Open Decisions Already Resolved

- Exchange: Binance Futures Testnet
- Trigger mode: polling
- Market context: current price plus recent candles
- Position sizing: percentage of demo balance
- Action set: `BUY`, `SELL`, `HOLD`, `CLOSE`

## Implementation Boundary

The next step after this design is to create a small implementation plan, then scaffold the Python worker and supporting modules.
