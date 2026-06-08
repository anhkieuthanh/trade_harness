# Environment Contract Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first environment contract layer for the current `BTCUSDT Binance Futures` agent so execution-safety guardrails are injected into both the runtime system prompt and Binance tool descriptions.

**Architecture:** Introduce a focused `runtime/contracts` module that centralizes contract wording and augmentation helpers. The runtime will compose the system prompt from the base prompt plus the environment contract, while the Binance toolset will request contract-enriched descriptions for each tool without changing the tool interface or execution behavior.

**Tech Stack:** Python 3, `unittest`, `compileall`, existing `tradeharness` runtime/tool architecture

---

## File Structure

- Create: `TradeHarness/tradeharness/runtime/contracts/__init__.py`
- Create: `TradeHarness/tradeharness/runtime/contracts/environment.py`
- Modify: `TradeHarness/tradeharness/tools/binance.py`
- Modify: `TradeHarness/tradeharness/runtime/agent.py`
- Modify: `TradeHarness/tests/test_agent_tools.py`
- Modify: `TradeHarness/README.MD`

## Implementation Notes

- Keep this phase prompt-level only. Do not add execution-blocking validation.
- Preserve existing tool names and response structures.
- Contract text must stay specialized to the current repo context: `BTCUSDT`, `Binance Futures Testnet`, and the current toolset.
- Keep the current dry-run and compatibility entrypoint behavior intact.

### Task 1: Add the contract module and verify its rendered content

**Files:**
- Create: `TradeHarness/tradeharness/runtime/contracts/__init__.py`
- Create: `TradeHarness/tradeharness/runtime/contracts/environment.py`
- Test: `TradeHarness/tests/test_agent_tools.py`

- [ ] **Step 1: Write the failing tests for contract rendering**

Append these tests to `tests/test_agent_tools.py`:

```python
from tradeharness.runtime.contracts.environment import (
    build_environment_contract,
    augment_tool_description,
)


class EnvironmentContractTests(unittest.TestCase):
    def test_build_environment_contract_mentions_execution_safety_rules(self) -> None:
        contract = build_environment_contract(symbol="BTCUSDT")

        self.assertIn("inspect market state before trading", contract)
        self.assertIn("get_position", contract)
        self.assertIn("Binance Futures Testnet", contract)

    def test_augment_tool_description_adds_tool_specific_contract(self) -> None:
        description = augment_tool_description(
            tool_name="open_long",
            base_description="Open a long futures position.",
        )

        self.assertIn("Open a long futures position.", description)
        self.assertIn("Only use after", description)
        self.assertIn("get_position", description)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: `ModuleNotFoundError` for `tradeharness.runtime.contracts.environment`.

- [ ] **Step 3: Create the contract package marker**

Create `tradeharness/runtime/contracts/__init__.py`:

```python
from tradeharness.runtime.contracts.environment import (
    augment_tool_description,
    build_environment_contract,
)

__all__ = ["augment_tool_description", "build_environment_contract"]
```

- [ ] **Step 4: Implement the environment contract module**

Create `tradeharness/runtime/contracts/environment.py`:

```python
from __future__ import annotations


BASE_EXECUTION_SAFETY_RULES = [
    "Inspect market state before trading.",
    "Inspect current position before opening or closing.",
    "Inspect available balance before opening exposure.",
    "Prefer observation tools before execution tools.",
    "Do not act with incomplete state.",
]


TOOL_CONTRACT_RULES = {
    "get_market_snapshot": [
        "Use this first to inspect recent price and candles.",
        "This is a state-inspection tool, not an execution tool.",
    ],
    "get_balance": [
        "Use this before opening exposure to confirm capital context.",
        "Do not assume sizing safety without checking balance.",
    ],
    "get_position": [
        "Use this before open_long, open_short, or close_position.",
        "Do not assume the account is flat without checking position.",
    ],
    "open_long": [
        "Only use after inspecting market state, position state, and balance.",
        "Do not use as a discovery step.",
    ],
    "open_short": [
        "Only use after inspecting market state, position state, and balance.",
        "Do not use as a discovery step.",
    ],
    "close_position": [
        "Only use after checking get_position.",
        "Do not call this unless an open position exists.",
    ],
}


def build_environment_contract(symbol: str) -> str:
    rules = "\n".join(f"- {rule}" for rule in BASE_EXECUTION_SAFETY_RULES)
    return "\n".join(
        [
            f"Environment Contract for {symbol} on Binance Futures Testnet:",
            rules,
            "Before requesting any execution tool, summarize what state was inspected and why the action follows.",
        ]
    )


def augment_tool_description(tool_name: str, base_description: str) -> str:
    rules = TOOL_CONTRACT_RULES.get(tool_name, [])
    if not rules:
        return base_description
    rule_lines = " ".join(rules)
    return f"{base_description} Contract: {rule_lines}"
```

- [ ] **Step 5: Run tests to verify the contract module passes**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: the two new contract tests pass, or any remaining failures point only to missing runtime/tool integration work.

### Task 2: Inject contract text into Binance tool descriptions

**Files:**
- Modify: `TradeHarness/tradeharness/tools/binance.py`
- Test: `TradeHarness/tests/test_agent_tools.py`

- [ ] **Step 1: Write the failing test for enriched tool definitions**

Append this test to `tests/test_agent_tools.py`:

```python
    def test_tool_definitions_include_contract_augmentation(self) -> None:
        toolset = BinanceToolset(FakeBinanceClient(), trade_size_percent=10.0)

        definitions = toolset.definitions()
        open_long = next(
            item for item in definitions if item["function"]["name"] == "open_long"
        )

        self.assertIn("Contract:", open_long["function"]["description"])
        self.assertIn("Only use after", open_long["function"]["description"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: the new test fails because tool descriptions still use plain base descriptions.

- [ ] **Step 3: Import the contract augmenter into the Binance toolset**

Add this import near the top of `tradeharness/tools/binance.py`:

```python
from tradeharness.runtime.contracts.environment import augment_tool_description
```

- [ ] **Step 4: Wrap each tool description with contract augmentation**

In `BinanceToolset.definitions()`, replace raw description strings with `augment_tool_description(...)`. For example:

```python
"description": augment_tool_description(
    tool_name="get_market_snapshot",
    base_description="Get current market snapshot for a symbol including latest price and recent candles.",
),
```

Apply the same pattern to:

- `get_balance`
- `get_position`
- `open_long`
- `open_short`
- `close_position`

- [ ] **Step 5: Run tests to verify tool descriptions now include contract text**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: all tool-definition and tool-behavior tests pass.

### Task 3: Inject the environment contract into the runtime system prompt

**Files:**
- Modify: `TradeHarness/tradeharness/runtime/agent.py`
- Test: `TradeHarness/tests/test_agent_tools.py`

- [ ] **Step 1: Write the failing test for composed system prompt**

Append these helpers and test to `tests/test_agent_tools.py`:

```python
from tradeharness.runtime.agent import build_system_prompt


class RuntimePromptTests(unittest.TestCase):
    def test_build_system_prompt_includes_environment_contract(self) -> None:
        prompt = build_system_prompt(symbol="BTCUSDT")

        self.assertIn("You are a BTCUSDT Binance Futures Testnet trading agent.", prompt)
        self.assertIn("Environment Contract for BTCUSDT on Binance Futures Testnet:", prompt)
        self.assertIn("Inspect market state before trading.", prompt)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: failure because `build_system_prompt` does not exist yet.

- [ ] **Step 3: Import the contract builder into the runtime**

Add this import to `tradeharness/runtime/agent.py`:

```python
from tradeharness.runtime.contracts.environment import build_environment_contract
```

- [ ] **Step 4: Replace the static system prompt constant with a prompt builder**

Replace the current `SYSTEM_PROMPT = """..."""` block with:

```python
BASE_SYSTEM_PROMPT = """You are a BTCUSDT Binance Futures Testnet trading agent.
Your brain runs in LM Studio. Your only way to inspect or act on Binance is through the provided tools.

Rules:
- Use tools to inspect market state, balance, and position before trading.
- Prefer get_market_snapshot, get_balance, and get_position before open_long, open_short, or close_position.
- If native tool calling is unavailable, return strict JSON like {"tool":"get_market_snapshot","arguments":{"symbol":"BTCUSDT","interval":"1m","limit":5}}.
- When you are done and no more tool calls are needed, return strict JSON like {"final":"short operator summary"}.
- Never mention tools that do not exist.
"""


def build_system_prompt(symbol: str) -> str:
    return "\n\n".join(
        [
            BASE_SYSTEM_PROMPT,
            build_environment_contract(symbol),
        ]
    )
```

Then update `messages` construction inside `run_agent_cycle(...)`:

```python
messages: list[dict[str, Any]] = [
    {"role": "system", "content": build_system_prompt(settings.symbol)},
    ...
]
```

- [ ] **Step 5: Run tests to verify the runtime prompt composition passes**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: the prompt-composition test passes along with the earlier contract and tool tests.

### Task 4: Update docs and verify dry-run behavior is preserved

**Files:**
- Modify: `TradeHarness/README.MD`

- [ ] **Step 1: Document the contract layer in the README**

Add this section after `## Package Layout` in `README.MD`:

```md
## Environment Contract Layer

The runtime includes a prompt-augmentation contract layer specialized for:

- `BTCUSDT`
- `Binance Futures Testnet`
- the current Binance toolset

This layer injects execution-safety guidance into:

- the runtime system prompt
- each Binance tool description

It is a guardrail and prompt-enrichment layer only in the current phase. It does not hard-block execution in code.
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

- at least one `tool=` line prints
- a final `agent=` line prints
- no real order is submitted

- [ ] **Step 4: Commit**

```bash
git add README.MD tradeharness/runtime/contracts tradeharness/runtime/agent.py tradeharness/tools/binance.py tests/test_agent_tools.py
git commit -m "feat: add environment contract layer"
```

## Self-Review

- Spec coverage check:
  - prompt augmentation only: covered by Tasks 1-3
  - execution-safety focus: covered by contract content in Tasks 1-3
  - system-prompt injection: covered by Task 3
  - tool-description injection: covered by Task 2
  - dry-run verification: covered by Task 4
- Placeholder scan: no `TODO`, `TBD`, or vague implementation markers remain.
- Type consistency: `build_environment_contract`, `augment_tool_description`, `build_system_prompt`, and `BinanceToolset.definitions()` are named consistently across tasks.
