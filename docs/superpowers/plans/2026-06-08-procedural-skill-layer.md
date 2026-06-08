# Procedural Skill Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first BM25-based procedural skill layer for the `BTCUSDT Binance Futures` agent so relevant entry-execution skills are retrieved from local repo data and injected into a `Relevant Skills` prompt block.

**Architecture:** Introduce a `runtime/skills` package with a local skill library, an in-memory BM25 retriever, and prompt helpers that build a context-rich retrieval query from user task, market snapshot, position state, and tool intent. The runtime will compose the final system prompt from the base system prompt, the environment contract, and the selected skills block, while preserving the existing tool-driven agent loop.

**Tech Stack:** Python 3, `unittest`, `compileall`, existing `tradeharness` runtime/tool architecture

---

## File Structure

- Create: `TradeHarness/tradeharness/runtime/skills/__init__.py`
- Create: `TradeHarness/tradeharness/runtime/skills/library.py`
- Create: `TradeHarness/tradeharness/runtime/skills/retrieval.py`
- Create: `TradeHarness/tradeharness/runtime/skills/prompting.py`
- Modify: `TradeHarness/tradeharness/runtime/agent.py`
- Modify: `TradeHarness/tests/test_agent_tools.py`
- Modify: `TradeHarness/README.MD`

## Implementation Notes

- Keep this phase retrieval-and-prompting only. Do not add execution blocking.
- Use local repo-defined skill records, not an external store.
- The first skill library should cover only entry execution.
- Implement a real BM25 scorer in Python for the current small corpus size.
- Preserve the existing dry-run behavior and compatibility entrypoint.

### Task 1: Add the local skill library and prompt rendering helpers

**Files:**
- Create: `TradeHarness/tradeharness/runtime/skills/__init__.py`
- Create: `TradeHarness/tradeharness/runtime/skills/library.py`
- Create: `TradeHarness/tradeharness/runtime/skills/prompting.py`
- Test: `TradeHarness/tests/test_agent_tools.py`

- [ ] **Step 1: Write the failing tests for the skill library and prompt block**

Append these tests to `tests/test_agent_tools.py`:

```python
from tradeharness.runtime.skills.library import get_skill_library
from tradeharness.runtime.skills.prompting import render_relevant_skills_block


class ProceduralSkillPromptingTests(unittest.TestCase):
    def test_skill_library_contains_entry_execution_skills(self) -> None:
        skills = get_skill_library()

        self.assertGreaterEqual(len(skills), 2)
        self.assertTrue(any("entry" in skill["title"].lower() for skill in skills))

    def test_render_relevant_skills_block_formats_skill_content(self) -> None:
        block = render_relevant_skills_block(
            [
                {
                    "skill_id": "entry_confirm",
                    "title": "Entry confirmation sequence",
                    "tags": ["entry", "btc"],
                    "when_to_use": "Before opening a new position.",
                    "procedure": "Inspect market, position, and balance before entry.",
                    "anti_patterns": "Do not jump straight to open_long.",
                }
            ]
        )

        self.assertIn("Relevant Skills:", block)
        self.assertIn("Entry confirmation sequence", block)
        self.assertIn("When to use:", block)
        self.assertIn("Anti-patterns:", block)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: `ModuleNotFoundError` for `tradeharness.runtime.skills.library` or `tradeharness.runtime.skills.prompting`.

- [ ] **Step 3: Create the skill package marker**

Create `tradeharness/runtime/skills/__init__.py`:

```python
from tradeharness.runtime.skills.library import get_skill_library
from tradeharness.runtime.skills.prompting import (
    build_skill_query,
    render_relevant_skills_block,
)
from tradeharness.runtime.skills.retrieval import retrieve_relevant_skills

__all__ = [
    "build_skill_query",
    "get_skill_library",
    "render_relevant_skills_block",
    "retrieve_relevant_skills",
]
```

- [ ] **Step 4: Add the seeded local skill library**

Create `tradeharness/runtime/skills/library.py`:

```python
from __future__ import annotations


def get_skill_library() -> list[dict[str, object]]:
    return [
        {
            "skill_id": "entry_confirm_state_first",
            "title": "Entry confirmation after state inspection",
            "tags": ["entry", "inspection", "btcusdt", "binance-futures"],
            "when_to_use": "Before calling open_long or open_short on BTCUSDT.",
            "procedure": (
                "Inspect market snapshot first, then inspect position state, then inspect balance. "
                "Only consider an entry after all three are consistent with the idea."
            ),
            "anti_patterns": (
                "Do not jump from user intent directly to open_long or open_short without "
                "market, position, and balance checks."
            ),
        },
        {
            "skill_id": "entry_thesis_short_summary",
            "title": "Short entry thesis before execution",
            "tags": ["entry", "thesis", "execution", "btcusdt"],
            "when_to_use": "Right before choosing open_long or open_short.",
            "procedure": (
                "Summarize what was inspected, what direction the recent state suggests, "
                "and why the execution tool matches that state."
            ),
            "anti_patterns": (
                "Do not use an execution tool when the inspected state is incomplete, "
                "contradictory, or not yet summarized."
            ),
        },
        {
            "skill_id": "entry_avoid_rushed_execution",
            "title": "Avoid rushed execution after observation",
            "tags": ["entry", "discipline", "execution-sequence"],
            "when_to_use": "When recent candles look active and the model wants to act quickly.",
            "procedure": (
                "Treat observation and execution as separate steps. After inspection, pause to "
                "form the execution intent before requesting an order tool."
            ),
            "anti_patterns": (
                "Do not treat get_market_snapshot alone as enough context for immediate execution."
            ),
        },
    ]
```

- [ ] **Step 5: Add prompt rendering helpers**

Create `tradeharness/runtime/skills/prompting.py`:

```python
from __future__ import annotations

import json
from typing import Any


def build_skill_query(
    *,
    user_task: str,
    symbol: str,
    interval: str,
    market_snapshot: dict[str, Any] | None,
    position_state: dict[str, Any] | None,
    tool_intent: str,
) -> str:
    snapshot_text = json.dumps(market_snapshot or {}, sort_keys=True)
    position_text = json.dumps(position_state or {}, sort_keys=True)
    return "\n".join(
        [
            f"User task: {user_task}",
            f"Symbol: {symbol}",
            f"Interval: {interval}",
            f"Market snapshot: {snapshot_text}",
            f"Position state: {position_text}",
            f"Tool intent: {tool_intent}",
        ]
    )


def render_relevant_skills_block(skills: list[dict[str, object]]) -> str:
    if not skills:
        return "Relevant Skills:\n- None selected."
    lines = ["Relevant Skills:"]
    for skill in skills:
        lines.extend(
            [
                f"- {skill['title']}",
                f"  When to use: {skill['when_to_use']}",
                f"  Procedure: {skill['procedure']}",
                f"  Anti-patterns: {skill['anti_patterns']}",
            ]
        )
    return "\n".join(lines)
```

- [ ] **Step 6: Run tests to verify the library and prompt helpers pass**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: the new skill-library and prompt-block tests pass, or any remaining failures point only to the missing retriever/runtime integration work.

### Task 2: Implement real BM25 retrieval for the local skill library

**Files:**
- Create: `TradeHarness/tradeharness/runtime/skills/retrieval.py`
- Test: `TradeHarness/tests/test_agent_tools.py`

- [ ] **Step 1: Write the failing retrieval tests**

Append these tests to `tests/test_agent_tools.py`:

```python
from tradeharness.runtime.skills.retrieval import retrieve_relevant_skills


class ProceduralSkillRetrievalTests(unittest.TestCase):
    def test_bm25_retrieval_prefers_entry_skill_for_open_long_query(self) -> None:
        results = retrieve_relevant_skills(
            query=(
                "user wants to open_long BTCUSDT after market inspection. "
                "Need entry execution guidance, inspect position and balance first."
            ),
            top_k=2,
        )

        self.assertGreaterEqual(len(results), 1)
        self.assertTrue(any("entry" in item["title"].lower() for item in results))

    def test_bm25_retrieval_limits_results_to_top_k(self) -> None:
        results = retrieve_relevant_skills(
            query="entry execution for btcusdt",
            top_k=1,
        )

        self.assertEqual(len(results), 1)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: `ModuleNotFoundError` for `tradeharness.runtime.skills.retrieval`.

- [ ] **Step 3: Implement the BM25 retriever**

Create `tradeharness/runtime/skills/retrieval.py`:

```python
from __future__ import annotations

import math
import re
from collections import Counter

from tradeharness.runtime.skills.library import get_skill_library


TOKEN_PATTERN = re.compile(r"[a-z0-9_:-]+")


def _tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def _skill_document(skill: dict[str, object]) -> str:
    return " ".join(
        str(skill[field])
        for field in ["title", "tags", "when_to_use", "procedure", "anti_patterns"]
    )


def retrieve_relevant_skills(query: str, top_k: int = 2) -> list[dict[str, object]]:
    skills = get_skill_library()
    documents = [_tokenize(_skill_document(skill)) for skill in skills]
    query_tokens = _tokenize(query)
    if not query_tokens:
        return skills[:top_k]

    doc_lengths = [len(doc) for doc in documents]
    avg_doc_length = sum(doc_lengths) / max(len(doc_lengths), 1)
    document_frequencies = Counter()
    for document in documents:
        for token in set(document):
            document_frequencies[token] += 1

    k1 = 1.5
    b = 0.75
    total_docs = len(documents)
    scored: list[tuple[float, dict[str, object]]] = []

    for skill, document in zip(skills, documents):
        term_counts = Counter(document)
        score = 0.0
        for token in query_tokens:
            if token not in term_counts:
                continue
            df = document_frequencies[token]
            idf = math.log(1 + ((total_docs - df + 0.5) / (df + 0.5)))
            tf = term_counts[token]
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * (len(document) / max(avg_doc_length, 1)))
            score += idf * (numerator / denominator)
        scored.append((score, skill))

    ranked = sorted(scored, key=lambda item: item[0], reverse=True)
    return [skill for score, skill in ranked[:top_k] if score > 0] or [skills[0]]
```

- [ ] **Step 4: Run tests to verify retrieval works**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: the BM25 retrieval tests pass along with all earlier tests.

### Task 3: Integrate skill retrieval into the runtime prompt composition

**Files:**
- Modify: `TradeHarness/tradeharness/runtime/agent.py`
- Test: `TradeHarness/tests/test_agent_tools.py`

- [ ] **Step 1: Write the failing runtime prompt test for relevant skills**

Append this test to `tests/test_agent_tools.py`:

```python
from tradeharness.runtime.skills.prompting import build_skill_query


class ProceduralSkillRuntimeIntegrationTests(unittest.TestCase):
    def test_build_skill_query_includes_task_state_and_tool_intent(self) -> None:
        query = build_skill_query(
            user_task="Inspect state then decide whether to open a position.",
            symbol="BTCUSDT",
            interval="1m",
            market_snapshot={"price": 63180.0},
            position_state={"side": "FLAT"},
            tool_intent="open_long",
        )

        self.assertIn("Inspect state then decide", query)
        self.assertIn("BTCUSDT", query)
        self.assertIn("open_long", query)
        self.assertIn('"price": 63180.0', query)
```

- [ ] **Step 2: Run tests to verify the current runtime has no skill injection yet**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: the new helper test passes after Task 1, but the runtime still does not inject a `Relevant Skills` block because no integration exists yet.

- [ ] **Step 3: Import skill retrieval helpers into the runtime**

Add these imports to `tradeharness/runtime/agent.py`:

```python
from tradeharness.runtime.skills.prompting import (
    build_skill_query,
    render_relevant_skills_block,
)
from tradeharness.runtime.skills.retrieval import retrieve_relevant_skills
```

- [ ] **Step 4: Add a composed prompt builder that includes relevant skills**

Replace the current `build_system_prompt(symbol: str)` function in `tradeharness/runtime/agent.py` with:

```python
def build_system_prompt(
    *,
    symbol: str,
    relevant_skills_block: str,
) -> str:
    return "\n\n".join(
        [
            BASE_SYSTEM_PROMPT,
            build_environment_contract(symbol),
            relevant_skills_block,
        ]
    )
```

- [ ] **Step 5: Gather state before the main agent loop and build the skill query**

Inside `run_agent_cycle(settings: Settings)`, add this state gathering before `messages` is created:

```python
    initial_market_snapshot = toolset.run_tool(
        "get_market_snapshot",
        {
            "symbol": settings.symbol,
            "interval": settings.candle_interval,
            "limit": settings.candle_limit,
        },
    )
    initial_position_state = toolset.run_tool(
        "get_position",
        {"symbol": settings.symbol},
    )
    skill_query = build_skill_query(
        user_task=(
            "Inspect state with tools first, then decide whether to trade."
        ),
        symbol=settings.symbol,
        interval=settings.candle_interval,
        market_snapshot=initial_market_snapshot,
        position_state=initial_position_state,
        tool_intent="entry_execution",
    )
    relevant_skills = retrieve_relevant_skills(skill_query, top_k=2)
    relevant_skills_block = render_relevant_skills_block(relevant_skills)
```

- [ ] **Step 6: Use the composed prompt with relevant skills**

Update `messages` construction in `run_agent_cycle(...)`:

```python
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": build_system_prompt(
                symbol=settings.symbol,
                relevant_skills_block=relevant_skills_block,
            ),
        },
        {
            "role": "user",
            "content": (
                f"Trade symbol {settings.symbol}. "
                f"Use interval {settings.candle_interval} and candle limit {settings.candle_limit}. "
                "Inspect state with tools first, then decide whether to trade."
            ),
        },
    ]
```

- [ ] **Step 7: Run tests to verify the runtime integration composes cleanly**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: all skill, contract, tool, and runtime prompt tests pass.

### Task 4: Update docs and verify the dry-run agent still operates correctly

**Files:**
- Modify: `TradeHarness/README.MD`

- [ ] **Step 1: Document the procedural skill layer**

Add this section below `## Environment Contract Layer` in `README.MD`:

```md
## Procedural Skill Layer

The runtime also includes a procedural skill layer for entry execution.

- skills are stored locally in the repo
- retrieval uses BM25 scoring in-memory
- the retrieval query is built from user task, market snapshot, position state, and tool intent
- selected skills are injected into the prompt under a `Relevant Skills` block

This phase focuses only on entry-execution guidance and does not yet include automatic skill distillation or execution blocking.
```

- [ ] **Step 2: Run compile verification**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m compileall tradeharness tests
```

Expected: all modules compile without syntax errors.

- [ ] **Step 3: Run the dry-run agent cycle**

Run:

```bash
cd /Users/atif/Public/TradeHarness
DRY_RUN=true python3 - <<'PY'
from tradeharness.main import run_once
run_once()
PY
```

Expected:

- the runtime still prints `tool=` lines and a final `agent=` line
- no real order is submitted
- the agent still operates normally with the new skill layer present

- [ ] **Step 4: Commit**

```bash
git add README.MD tradeharness/runtime/skills tradeharness/runtime/agent.py tests/test_agent_tools.py
git commit -m "feat: add procedural skill layer"
```

## Self-Review

- Spec coverage check:
  - local skill library: covered by Task 1
  - BM25 retrieval: covered by Task 2
  - query from task + market + position + tool intent: covered by Task 3
  - `Relevant Skills` injection block: covered by Tasks 1 and 3
  - dry-run verification: covered by Task 4
- Placeholder scan: no `TODO`, `TBD`, or vague implementation markers remain.
- Type consistency: `get_skill_library`, `build_skill_query`, `render_relevant_skills_block`, `retrieve_relevant_skills`, and `build_system_prompt` are named consistently across tasks.
