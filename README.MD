# TradeHarness

Minimal local agent bridge between LM Studio and Binance Futures Testnet for `BTCUSDT`.

## Package Layout

- `tradeharness/config/`: runtime settings
- `tradeharness/domain/`: shared data contracts
- `tradeharness/integrations/binance/`: low-level Binance client
- `tradeharness/integrations/evaluator/`: OpenAI-compatible evaluator client for offline evolution
- `tradeharness/integrations/lmstudio/`: LM Studio client and tool-request parsing
- `tradeharness/tools/`: Binance tools exposed to the agent
- `tradeharness/runtime/`: agent orchestration loop
- `tradeharness/evolution/`: offline evolution, FAP, update candidates, regression notes

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

## Offline Evolution Block

The repo now also includes an offline evolution block.

- the runtime writes trajectory episodes to `TRAJECTORY_LOG_PATH`
- offline evolution reads those episodes after the session
- it runs a Failure Annotation Protocol cascade
- it maps failures into LIFE-HARNESS layers
- it mines recurring failure patterns
- it writes staged layer artifacts
- it promotes additive safe updates into active Layer 1 and Layer 2 artifacts

This first phase uses an external `OpenAI-compatible` evaluator endpoint configured through:

- `EVALUATOR_BASE_URL`
- `EVALUATOR_API_KEY`
- `EVALUATOR_MODEL`

Additional evolution settings:

- `EVOLUTION_RUNS_DIR`
- `EVOLUTION_MINIMUM_SUPPORT`
- `ACTIVE_CONTRACT_ARTIFACT_PATH`
- `ACTIVE_SKILLS_ARTIFACT_PATH`
- `ACTIVE_ACTION_RULES_ARTIFACT_PATH`
- `ACTIVE_TRAJECTORY_RULES_ARTIFACT_PATH`
- `ACTIVE_HARNESS_META_ARTIFACT_PATH`
- `CONTROL_STATE_PATH`

Pass metrics settings:

- `HARNESS_VERSION`
- `TASK_ID`

Runtime versioning behavior:

- `HARNESS_VERSION` is now a fallback/manual seed only
- runtime prefers the promoted meta artifact at `ACTIVE_HARNESS_META_ARTIFACT_PATH`
- offline evolution bumps harness version automatically after a successful promotion

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
- `EVALUATOR_API_KEY`

LM Studio defaults:

- URL: `http://192.168.10.17:1234/v1`
- Model: `google/gemma-4-e2b`

## Run

All-in-one local server, UI, and scheduler:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m tradeharness.supervisor
```

This starts:

- the Streamlit operator UI on `http://localhost:8501`
- a background supervisor loop
- the live agent loop when it is enabled from the UI
- the offline evolution schedule configured from the UI

Manual single-cycle dry run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m tradeharness.main
```

Real demo order mode:

Set `DRY_RUN=false` in `.env`, run `python3 -m tradeharness.supervisor`, then enable the live loop from the UI.

Default live strategy:

- `TRADE_STRATEGY_MODE=random_flip`
- opens a random `LONG` or `SHORT` when flat
- uses fixed size `TRADE_ENTRY_QUANTITY_BTC=0.008`
- closes the position after `TRADE_HOLD_SECONDS=120`
- optional cooldown before the next entry: `TRADE_COOLDOWN_SECONDS`
- persists its timer state in `TRADE_STRATEGY_STATE_PATH`

Live risk guard:

- `TRADE_RISK_MAX_DAILY_LOSS_USDT`
- `TRADE_RISK_MAX_OPEN_POSITIONS`
- `TRADE_RISK_LOSS_COOLDOWN_SECONDS`
- `TRADE_RISK_HARD_STOP_CANDLE_RANGE_PCT`
- runtime risk state is stored in `TRADE_RISK_STATE_PATH`

Offline evolution batch:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m tradeharness.evolution.main
```

This produces:

- a daily markdown report
- annotated failure JSON
- pass metrics JSON with `Pass@1`
- mined failure patterns
- layer update candidates
- staged layer artifacts
- regression check notes
- promotion report

Daily scheduled-style batch:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m tradeharness.evolution.scheduler
```

This writes a dated run snapshot under `EVOLUTION_RUNS_DIR`, for example:

- `var/evolution/runs/2026-06-08/`

Active additive artifacts are promoted into:

- `tradeharness/evolution/artifacts/current/contract.json`
- `tradeharness/evolution/artifacts/current/skills.json`
- `tradeharness/evolution/artifacts/current/harness_meta.json`

Layer 3 and Layer 4 can also rehydrate active deterministic artifacts when present:

- `tradeharness/evolution/artifacts/current/action_rules.json`
- `tradeharness/evolution/artifacts/current/trajectory_rules.json`

## Streamlit Monitor

The preferred way to run the local operator console is through the supervisor:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m tradeharness.supervisor
```

The page shows runtime health, recent episodes, evolution artifacts, and safe operator controls.
Each data section refreshes independently, so changing one source does not force a full-page refresh.

The UI can:

- enable or disable the live agent loop
- enable or disable scheduled offline evolution
- set the daily offline evolution time
- trigger offline evolution manually

The control state is stored at `CONTROL_STATE_PATH`, defaulting to:

- `var/control/state.json`

For UI-only debugging, you can still run:

```bash
cd /Users/atif/Public/TradeHarness
streamlit run streamlit_app.py
```

## Pass Metrics

The offline evolution block now tracks one harness-level success metric:

- `Pass@1`: percentage of episodes that finish successfully on a single run

## Scheduling

Two local scheduling options are supported for the daily evolution batch.

### Cron

Example daily run at 01:00:

```cron
0 1 * * * cd /Users/atif/Public/TradeHarness && /usr/bin/python3 -m tradeharness.evolution.scheduler >> /Users/atif/Public/TradeHarness/var/evolution/cron.log 2>&1
```

### launchd

Use the template at:

- `ops/launchd/com.tradeharness.evolution.plist`

Load it with:

```bash
launchctl unload ~/Library/LaunchAgents/com.tradeharness.evolution.plist 2>/dev/null || true
cp /Users/atif/Public/TradeHarness/ops/launchd/com.tradeharness.evolution.plist ~/Library/LaunchAgents/com.tradeharness.evolution.plist
launchctl load ~/Library/LaunchAgents/com.tradeharness.evolution.plist
```

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
