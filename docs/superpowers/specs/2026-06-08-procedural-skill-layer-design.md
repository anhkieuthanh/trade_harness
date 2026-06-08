# Procedural Skill Layer Design

## Goal

Add the second LIFE-HARNESS layer to `TradeHarness`: the `Procedural Skill Layer`.

For this repo, the first version will support the current `BTCUSDT Binance Futures` agent by retrieving concise procedural skills that improve entry execution behavior.

This layer is not about changing model weights. It is a retrieval-and-injection layer that gives the agent relevant, field-tested procedural guidance before it chooses or calls tools.

## Core Idea

If the first layer (`Environment Contract Layer`) defines the rules of engagement, the second layer provides the practical playbook for handling a task well.

In this repo, a skill is a short, reusable procedural strategy for a specific trading situation.

Examples of the kind of skills this layer should support:

- inspect state before entry and confirm context
- avoid opening a position with incomplete state
- follow a consistent entry evaluation sequence before execution

## Phase Boundary

This first version will:

- use real BM25-style retrieval
- store skills locally in the repo
- build the retrieval query from live runtime context
- inject the selected skills into the prompt as a distinct `Relevant Skills` block
- focus only on `entry execution` skills

This first version will not:

- perform automatic skill distillation from forward tests
- cover position management or recovery workflows yet
- add execution blocking
- add a database or external search service

## Skill Shape

Each skill record should contain structured text fields such as:

- `skill_id`
- `title`
- `tags`
- `when_to_use`
- `procedure`
- `anti_patterns`

These fields should be easy to render into a searchable text document for BM25 scoring and easy to inject back into the prompt as readable guidance.

## Retrieval Strategy

The first version should use BM25 retrieval directly, not rule-based fallback.

The query should be built from:

- user task
- market snapshot
- position state
- current or likely tool intent

This richer query is important because the value of BM25 depends on how much real context the query carries.

## Injection Strategy

Retrieved skills should not be mixed invisibly into the system prompt body.

They should be injected in a distinct prompt section such as:

```text
Relevant Skills:
- ...
- ...
```

This makes the augmentation explicit, easier to debug, and easier to evolve later.

The prompt composition should therefore include:

1. base system prompt
2. environment contract
3. relevant skills block

## First Skill Scope: Entry Execution

The initial skill library should focus only on entry execution.

The first seeded skills should guide behaviors such as:

- inspect market, position, and balance before opening exposure
- avoid rushing from observation to execution
- form a short entry thesis before calling `open_long` or `open_short`
- avoid opening a position when the inspected state is incomplete or contradictory

These should be procedural and practical, not abstract trading philosophy.

## Proposed Code Shape

This layer should live near runtime orchestration because it is part of context assembly:

```text
tradeharness/runtime/skills/
  __init__.py
  library.py
  retrieval.py
  prompting.py
```

Responsibilities:

- `library.py`: local skill records
- `retrieval.py`: BM25 scoring and top-k selection
- `prompting.py`: query building and prompt rendering

## Runtime Integration

At runtime the agent loop should:

1. inspect current state or gather the context needed to form a retrieval query
2. build the retrieval query from:
   - user task
   - symbol and interval context
   - position state
   - current/likely tool intent
3. retrieve the top-k relevant skills
4. inject them into the system prompt in a `Relevant Skills` block
5. continue with the existing tool-driven agent flow

This should be a prompt-augmentation improvement, not a redesign of the overall runtime loop.

## Skill Source For This Phase

The first version will seed the library manually inside the repo.

That still aligns with the intended architecture because the data model can later accept automatically distilled skills from evaluation or evolution workflows.

The important part now is to define:

- the skill record format
- the retrieval mechanism
- the injection path

## Non-Goals

This change should not:

- add automatic skill distillation yet
- add multi-layer policy enforcement
- change the Binance tool interface
- introduce vector search
- add position-management or recovery skills in this phase

## Why This Layer Matters

The agent can already use tools and already has a contract layer, but it still lacks reusable procedural experience.

This layer fills that gap by telling the model:

- not just what is allowed
- but also what execution sequence is most reliable in this environment

That should reduce wandering reasoning and make entry behavior more consistent.

## Implementation Boundary

The next step is to write an implementation plan for:

- creating the local skill library
- implementing BM25 retrieval
- building retrieval queries from runtime context
- injecting a `Relevant Skills` block into the composed prompt
- verifying the dry-run agent still operates correctly
