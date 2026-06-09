# Streamlit Live Monitor Design

## Goal

Upgrade the existing `streamlit_app.py` into a simple single-page operator console for live monitoring and safe operational controls while the TradeHarness runtime is running.

The dashboard is for human oversight, not for direct discretionary trading. It should help the operator answer:

- Is the runtime alive?
- What happened in the latest episode?
- Is harness health improving or drifting?
- Can I safely trigger housekeeping actions like offline evolution without opening a shell?

## Scope

This design covers:

- live runtime visibility from `var/trajectories/episodes.jsonl`
- passive visibility into evolution artifacts under `var/evolution/`
- safe operator controls only
- manual refresh behavior

This design explicitly does **not** include:

- direct trade buttons like `open_long` / `open_short`
- editing `.env` values from the UI
- process supervision with hard guarantees
- multi-page Streamlit navigation

## Chosen Approach

Use a **single-page operator console** by extending the existing [streamlit_app.py](/Users/atif/Public/TradeHarness/streamlit_app.py:1).

Why this approach:

- the repo already has a useful baseline monitor
- it keeps the MVP small and easy to run locally
- it matches the current operational need better than a tabbed or multi-page app
- it avoids adding stateful UI complexity before the runtime itself has a stronger process manager

## Page Structure

The page stays single-screen and top-to-bottom in this order:

1. Header bar
2. Runtime status
3. Latest episode details
4. Recent activity table
5. Harness and evolution summary
6. Safe operator controls
7. Raw payload inspector

## Section Design

### 1. Header Bar

Purpose: establish operator context immediately.

Displayed items:

- app title
- current symbol
- current mode
- current `harness_version`
- current `task_id`
- trajectory log path
- manual `Refresh now` button

The current `harness_version` should be read from the same runtime-facing resolution path as the app itself:

- prefer `tradeharness/evolution/artifacts/current/harness_meta.json`
- fallback to `.env` if the meta artifact is missing

### 2. Runtime Status

Purpose: tell the operator whether the live loop is healthy.

Displayed metrics:

- runtime status: `ALIVE` or `STALE/DEAD`
- total episode count
- last cycle end time
- age since latest cycle
- stale threshold
- poll interval
- `Pass@1` over recent episodes

Rules:

- `Pass@1` is computed from recent episodes only, not all historical data, to make drift visible
- the default evaluation window should be the most recent 20 episodes
- if there are no episodes, show a warning rather than zero-like fake values

### 3. Latest Episode Details

Purpose: make the newest cycle easy to diagnose without opening raw JSON first.

Displayed items:

- final status
- termination reason
- step count
- latest tool or final response
- latest harness decision
- started and ended timestamps
- concise operator note inferred from the newest episode

Also add one compact step table for the latest episode with:

- step index
- requested tool or final response
- harness decision
- short environment feedback preview

### 4. Recent Activity Table

Purpose: let the operator scan the latest runtime behavior quickly.

Displayed rows:

- latest 15 episodes in reverse chronological order

Columns:

- ended time
- final status
- termination
- steps
- latest tool
- harness decision
- mode
- short episode id

### 5. Harness And Evolution Summary

Purpose: connect live runtime behavior to the offline evolution block.

Displayed items:

- latest promoted harness version from `harness_meta.json`
- latest evolution daily report timestamp if available
- count of current annotations, candidates, and regression notes if files exist
- quick preview of the latest `daily-report.md`
- quick preview of `pass-metrics.json`

This gives the operator one place to see both:

- what the runtime is doing now
- what the offline system last concluded

### 6. Safe Operator Controls

Purpose: allow lightweight operational actions without enabling direct trade entry.

Allowed controls:

- `Refresh now`
- `Run offline evolution now`
- `Reload evolution artifacts`

Command behavior:

- `Run offline evolution now` should run the same command as the documented batch flow:
  - `python3 -m tradeharness.evolution.main`
- capture stdout/stderr and render it in the page
- show success/failure clearly

Not included:

- start/stop runtime buttons
- tool invocation buttons for Binance actions
- config editing controls

Reasoning:

- the current repo does not yet expose a durable runtime supervisor API
- direct process control from Streamlit would be brittle
- safe ops should remain focused on read/refresh/evolution actions

### 7. Raw Payload Inspector

Purpose: preserve full debugging visibility.

Displayed items:

- raw JSON of the latest episode
- optional selector to inspect one recent episode by `episode_id`

This keeps the operator from needing to open `episodes.jsonl` manually during troubleshooting.

## Data Sources

### Runtime

- `var/trajectories/episodes.jsonl`
- `.env`
- `tradeharness/evolution/artifacts/current/harness_meta.json`

### Evolution

- `var/evolution/daily-report.md`
- `var/evolution/annotations.json`
- `var/evolution/candidates.json`
- `var/evolution/regression-notes.json`
- `var/evolution/pass-metrics.json`
- latest dated run under `var/evolution/runs/YYYY-MM-DD/` when available

## Code Structure

Keep the app in [streamlit_app.py](/Users/atif/Public/TradeHarness/streamlit_app.py:1) for this phase, but refactor into clearer helpers.

Recommended helper groups:

- environment and settings loaders
- trajectory parsing and episode summarization
- quick metrics helpers like recent `Pass@1`
- evolution artifact loaders
- safe ops command runner
- rendering helpers per section

No additional UI framework or multi-file page system is required for this MVP.

## Error Handling

The dashboard must fail soft.

Rules:

- missing files should render warnings, not crash the page
- malformed JSON lines should be skipped with a warning count if practical
- failed offline evolution runs should show captured stderr/stdout in the UI
- if the evolution artifacts are absent, the evolution summary should degrade gracefully

## Testing Strategy

Testing focus should stay on deterministic helpers, not Streamlit internals.

Add tests for:

- harness version resolution from meta artifact fallback chain
- recent `Pass@1` computation
- latest evolution artifact discovery
- output parsing for safe command execution helpers

Manual verification:

- run Streamlit locally
- confirm the page renders with the current `episodes.jsonl`
- confirm refresh works
- confirm `Run offline evolution now` updates the visible evolution summary

## Success Criteria

The design is successful when an operator can open the page and answer these questions within a few seconds:

- Is the runtime alive?
- Did the latest cycle succeed or fail?
- What did the harness just allow or block?
- What is the current harness version?
- What did the latest offline evolution run recommend?
- Can I trigger a fresh offline evolution run without leaving the dashboard?
