# TradeHarness System Timeline And Flow

## Goal

This note gives a visual overview of how the full `TradeHarness` system runs across a normal day.

It combines:

- the continuous online trading loop
- the daily offline evolution batch
- the handoff points between runtime behavior and harness improvement

## 24h Timeline

Assumptions for the current repo:

- online runtime is started manually
- online runtime loops forever
- one online cycle runs every `POLL_INTERVAL_SECONDS`
- offline evolution is scheduled once per day at `01:00`
- offline evolution reads the accumulated trajectory log and produces the next harness artifacts

```text
Time (24h)

00:00        01:00                           Daytime                                 23:59
|------------|--------------------------------------------------------------------------|
             |
             +--> Offline Evolution Scheduler
                  - read `var/trajectories/episodes.jsonl`
                  - run FAP
                  - map failures to layers
                  - mine recurring patterns
                  - write staged artifacts
                  - run regression gate
                  - promote safe Layer 1/2 artifacts into `current/`


Online Runtime Window (whenever the process is running)

Start process
|
v
+-------------------- repeated forever --------------------+
| load settings                                           |
| run one agent cycle                                     |
| append trajectory episode to JSONL                      |
| sleep `POLL_INTERVAL_SECONDS`                           |
+---------------------------------------------------------+
```

## Online Runtime Loop

The online loop is the live or demo trading process.

Current entrypoint:

- `python3 -m tradeharness.main`

Current runtime shape:

```text
tradeharness.main
  -> tradeharness.runtime.main.main()
       -> while True:
            run_once()
            sleep(POLL_INTERVAL_SECONDS)
```

Each `run_once()` does:

```text
Load Settings
  -> Start one agent cycle
     -> Build system prompt
     -> Apply Layer 1 contract
     -> Inject Layer 2 skills
     -> Let LM Studio decide tools
     -> Validate execution with Layer 3
     -> Monitor trajectory with Layer 4
     -> Emit final result
     -> Write one trajectory episode to JSONL
```

## Offline Evolution Loop

The offline loop is the daily learning and harness-improvement process.

Current entrypoint:

- `python3 -m tradeharness.evolution.scheduler`

Current scheduled time in repo templates:

- `01:00` every day

Current scheduler shape:

```text
Scheduler Trigger
  -> load settings
  -> derive run directory: `var/evolution/runs/YYYY-MM-DD/`
  -> create evaluator client
  -> call `run_offline_evolution(...)`
```

## Full System Flow

```text
                           ONLINE RUNTIME
                           --------------

User starts runtime
   |
   v
+-------------------------+
| LM Studio Trading Agent |
+-------------------------+
   |
   v
+-------------------------------+
| Layer 1: Environment Contract |
+-------------------------------+
   |
   v
+-----------------------------+
| Layer 2: Procedural Skills  |
+-----------------------------+
   |
   v
+-----------------------------+
| Layer 3: Action Realization |
+-----------------------------+
   |
   v
+------------------------------+
| Layer 4: Trajectory Monitor  |
+------------------------------+
   |
   v
+-----------------------------------------------+
| Episode written to `var/trajectories/*.jsonl` |
+-----------------------------------------------+


                           OFFLINE EVOLUTION
                           -----------------

Daily scheduler / manual batch
   |
   v
+----------------------------------------------+
| Read trajectory episodes from previous runs  |
+----------------------------------------------+
   |
   v
+-------------------------------+
| FAP diagnostic cascade        |
| - action realization          |
| - environment contract        |
| - trajectory degeneration     |
| - residual reasoning          |
+-------------------------------+
   |
   v
+------------------------------+
| Four-layer classification    |
+------------------------------+
   |
   v
+------------------------------+
| Failure pattern mining       |
+------------------------------+
   |
   v
+------------------------------+
| Evo updater / coding agent   |
+------------------------------+
   |
   v
+------------------------------+
| Staged artifacts             |
| - contract.json              |
| - skills.json                |
| - action_rules.json          |
| - trajectory_rules.json      |
+------------------------------+
   |
   v
+------------------------------+
| Regression + promotion gate  |
+------------------------------+
   |
   +-------------------- promote safe additive updates --------------------+
   |                                                                       |
   v                                                                       v
`tradeharness/evolution/artifacts/current/contract.json`       `.../current/skills.json`

                These are reloaded by the next online runtime cycle.
```

## Current Scheduling Behavior

### Online

- continuous loop
- frequency controlled by `POLL_INTERVAL_SECONDS`
- no built-in stop time or market-hours calendar yet

### Offline

- one batch per day
- current templates set it to `01:00`

Repo templates:

- cron: `ops/cron/tradeharness-evolution.cron`
- launchd: `ops/launchd/com.tradeharness.evolution.plist`

## Artifact Handoff

The current handoff between online and offline is:

```text
Online runtime
  -> writes trajectory episodes
Offline evolution
  -> reads those episodes
  -> promotes safe Layer 1/2 artifacts
Next runtime cycle
  -> rehydrates active Layer 1/2 artifacts
```

The repo now also supports rehydration hooks for:

- Layer 3 action rules
- Layer 4 trajectory rules

but those layers still need higher-quality promoted artifacts before they materially change runtime behavior.

## What Is Running Automatically Today

If you enable a scheduler:

- online runtime: only if you start the process yourself
- offline evolution: yes, once daily at `01:00`

If you do not enable a scheduler:

- online runtime: manual start
- offline evolution: manual start

## Practical Daily Sequence

The intended operating sequence for a normal day is:

```text
1. Keep online runtime running during the period you want to collect trajectories.
2. Let the runtime append episodes to `var/trajectories/episodes.jsonl`.
3. At 01:00, run the offline scheduler.
4. Scheduler writes a dated run snapshot under `var/evolution/runs/YYYY-MM-DD/`.
5. Safe Layer 1/2 updates are promoted into `tradeharness/evolution/artifacts/current/`.
6. The next online runtime process uses the improved active artifacts.
```

## Current Limits

The current timeline is operational, but still simple:

- no market-session calendar
- no intra-day evolution batches
- no automatic process supervisor for the online runtime
- no multi-stage human approval gate before promotion
- no fully active Layer 3/4 promotion loop yet
