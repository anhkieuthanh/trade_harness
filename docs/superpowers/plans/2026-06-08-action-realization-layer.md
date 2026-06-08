# Action Realization Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first deterministic action-realization gate so invalid execution actions are blocked before they reach Binance, with structured feedback returned to the LLM and a retry limit that prevents infinite correction loops.

**Architecture:** Introduce a focused `runtime/action_realization` package that evaluates execution-tool requests using deterministic state evidence from the current loop. The runtime will call this gate before any execution tool, append block feedback back into the conversation when needed, and stop after a small configured number of blocked retries.

**Tech Stack:** Python 3, `unittest`, `compileall`, existing `tradeharness` runtime/tool architecture

---

## File Structure

- Create: `TradeHarness/tradeharness/runtime/action_realization/__init__.py`
- Create: `TradeHarness/tradeharness/runtime/action_realization/gate.py`
- Modify: `TradeHarness/tradeharness/runtime/agent.py`
- Modify: `TradeHarness/tests/test_agent_tools.py`
- Modify: `TradeHarness/README.MD`

## Implementation Notes

- Keep this phase deterministic and code-based. Do not push the check back into prompt logic.
- Gate only execution tools in the first version: `open_long`, `open_short`, `close_position`.
- Observation tools remain executable without gate blocking.
- The retry limit should be explicit in code and small, such as `2`.
- Preserve the existing dry-run mode and compatibility entrypoint.

### Task 1: Add the deterministic gate module and prove its decisions with tests

**Files:**
- Create: `TradeHarness/tradeharness/runtime/action_realization/__init__.py`
- Create: `TradeHarness/tradeharness/runtime/action_realization/gate.py`
- Test: `TradeHarness/tests/test_agent_tools.py`

- [ ] **Step 1: Write the failing gate tests**

Append these tests to `tests/test_agent_tools.py`:

```python
from tradeharness.runtime.action_realization.gate import realize_action


class ActionRealizationGateTests(unittest.TestCase):
    def test_blocks_close_position_when_state_is_flat(self) -> None:
        result = realize_action(
            tool_name="close_position",
            arguments={"symbol": "BTCUSDT"},
            position_state={"side": "FLAT", "is_open": False},
            inspected_state={
                "market_snapshot": True,
                "position": True,
                "balance": True,
            },
        )

        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("No open position", result["reason"])

    def test_blocks_open_long_when_position_is_already_open(self) -> None:
        result = realize_action(
            tool_name="open_long",
            arguments={"symbol": "BTCUSDT"},
            position_state={"side": "LONG", "is_open": True},
            inspected_state={
                "market_snapshot": True,
                "position": True,
                "balance": True,
            },
        )

        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("already open", result["reason"])

    def test_blocks_execution_when_required_state_was_not_inspected(self) -> None:
        result = realize_action(
            tool_name="open_short",
            arguments={"symbol": "BTCUSDT"},
            position_state={"side": "FLAT", "is_open": False},
            inspected_state={
                "market_snapshot": True,
                "position": False,
                "balance": True,
            },
        )

        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("position", result["reason"].lower())

    def test_allows_open_long_when_state_is_flat_and_fully_inspected(self) -> None:
        result = realize_action(
            tool_name="open_long",
            arguments={"symbol": "BTCUSDT"},
            position_state={"side": "FLAT", "is_open": False},
            inspected_state={
                "market_snapshot": True,
                "position": True,
                "balance": True,
            },
        )

        self.assertEqual(result["decision"], "EXECUTE")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: `ModuleNotFoundError` for `tradeharness.runtime.action_realization.gate`.

- [ ] **Step 3: Create the package marker**

Create `tradeharness/runtime/action_realization/__init__.py`:

```python
from tradeharness.runtime.action_realization.gate import (
    EXECUTION_TOOL_NAMES,
    MAX_ACTION_REALIZATION_RETRIES,
    realize_action,
)

__all__ = [
    "EXECUTION_TOOL_NAMES",
    "MAX_ACTION_REALIZATION_RETRIES",
    "realize_action",
]
```

- [ ] **Step 4: Implement the action-realization gate**

Create `tradeharness/runtime/action_realization/gate.py`:

```python
from __future__ import annotations

from typing import Any


EXECUTION_TOOL_NAMES = {"open_long", "open_short", "close_position"}
MAX_ACTION_REALIZATION_RETRIES = 2


def realize_action(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    position_state: dict[str, Any],
    inspected_state: dict[str, bool],
) -> dict[str, Any]:
    if tool_name not in EXECUTION_TOOL_NAMES:
        return {
            "decision": "EXECUTE",
            "reason": "Observation tool does not require action realization blocking.",
            "details": {"tool_name": tool_name},
        }

    missing_checks = [
        label
        for label, was_seen in inspected_state.items()
        if label in {"market_snapshot", "position", "balance"} and not was_seen
    ]
    if missing_checks:
        return {
            "decision": "BLOCK",
            "reason": (
                "Execution blocked because required state was not inspected: "
                + ", ".join(missing_checks)
            ),
            "details": {
                "tool_name": tool_name,
                "missing_checks": missing_checks,
                "arguments": arguments,
            },
        }

    side = str(position_state.get("side", "FLAT")).upper()
    is_open = bool(position_state.get("is_open", False))

    if tool_name == "close_position" and not is_open:
        return {
            "decision": "BLOCK",
            "reason": "No open position is available to close.",
            "details": {"tool_name": tool_name, "position_state": position_state},
        }

    if tool_name in {"open_long", "open_short"} and is_open:
        return {
            "decision": "BLOCK",
            "reason": f"An open position is already open ({side}); do not open another entry action now.",
            "details": {"tool_name": tool_name, "position_state": position_state},
        }

    return {
        "decision": "EXECUTE",
        "reason": "Action passed state-validity checks.",
        "details": {"tool_name": tool_name},
    }
```

- [ ] **Step 5: Run tests to verify gate behavior now passes**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: the new gate tests pass, or any remaining failures point only to runtime wiring work.

### Task 2: Wire the gate into the runtime loop with block feedback

**Files:**
- Modify: `TradeHarness/tradeharness/runtime/agent.py`
- Test: `TradeHarness/tests/test_agent_tools.py`

- [ ] **Step 1: Write the failing runtime helper test for block feedback formatting**

Append these tests to `tests/test_agent_tools.py`:

```python
from tradeharness.runtime.agent import build_action_block_feedback


class ActionRealizationRuntimeTests(unittest.TestCase):
    def test_build_action_block_feedback_contains_block_reason(self) -> None:
        feedback = build_action_block_feedback(
            {
                "decision": "BLOCK",
                "reason": "No open position is available to close.",
                "details": {"tool_name": "close_position"},
            }
        )

        self.assertIn("Action blocked", feedback)
        self.assertIn("No open position is available to close.", feedback)
        self.assertIn("corrected action", feedback.lower())
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: failure because `build_action_block_feedback` does not exist yet.

- [ ] **Step 3: Import the gate into the runtime**

Add these imports to `tradeharness/runtime/agent.py`:

```python
from tradeharness.runtime.action_realization.gate import (
    EXECUTION_TOOL_NAMES,
    MAX_ACTION_REALIZATION_RETRIES,
    realize_action,
)
```

- [ ] **Step 4: Add a helper for block feedback text**

Add this function to `tradeharness/runtime/agent.py` above `run_agent_cycle(...)`:

```python
def build_action_block_feedback(block_result: dict[str, Any]) -> str:
    return (
        "Action blocked by Action Realization Layer. "
        f"Reason: {block_result['reason']} "
        "Please inspect the latest state and propose a corrected action or return a final no-trade summary."
    )
```

- [ ] **Step 5: Track inspected state and blocked retries in the runtime**

Inside `run_agent_cycle(settings: Settings)`, after the initial state gathering block, add:

```python
    inspected_state = {
        "market_snapshot": True,
        "position": True,
        "balance": False,
    }
    blocked_attempts = 0
```

Then, inside the `for _ in range(6):` loop, before executing each tool request, insert:

```python
                if tool_request.name == "get_market_snapshot":
                    inspected_state["market_snapshot"] = True
                elif tool_request.name == "get_position":
                    inspected_state["position"] = True
                elif tool_request.name == "get_balance":
                    inspected_state["balance"] = True

                current_position_state = toolset.run_tool(
                    "get_position",
                    {"symbol": settings.symbol},
                )

                gate_result = realize_action(
                    tool_name=tool_request.name,
                    arguments=tool_request.arguments,
                    position_state=current_position_state,
                    inspected_state=inspected_state,
                )

                if gate_result["decision"] == "BLOCK":
                    blocked_attempts += 1
                    messages.append(assistant_message)
                    messages.append(
                        {
                            "role": "user",
                            "content": build_action_block_feedback(gate_result),
                        }
                    )
                    print(f"action_realization=BLOCK result={json.dumps(gate_result)}")
                    if blocked_attempts > MAX_ACTION_REALIZATION_RETRIES:
                        print('agent={"final":"blocked_by_action_realization_limit"}')
                        return
                    break
```

Place this block ahead of `toolset.run_tool(...)`.

- [ ] **Step 6: Preserve normal execution when the gate returns `EXECUTE`**

Keep the existing execution branch for allowed actions, but ensure it only runs after the gate check passes.

- [ ] **Step 7: Run tests to verify runtime helpers and imports pass**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: helper and gate tests pass, and there are no regressions in earlier tests.

### Task 3: Correct the runtime loop structure so blocked actions re-prompt safely

**Files:**
- Modify: `TradeHarness/tradeharness/runtime/agent.py`

- [ ] **Step 1: Refactor the per-tool loop to distinguish blocked vs executed paths**

Inside the `if tool_requests:` branch, introduce a flag before iterating:

```python
            blocked_in_this_turn = False
```

When a gate result is `BLOCK`, set:

```python
                    blocked_in_this_turn = True
```

and `break` the tool-request loop.

- [ ] **Step 2: Skip normal continuation when a block already re-prompted the model**

After the `for tool_request in tool_requests:` loop, add:

```python
            if blocked_in_this_turn:
                continue
```

This ensures the runtime starts the next LLM turn instead of falling through the current execution path incorrectly.

- [ ] **Step 3: Only append the assistant message once per blocked turn**

Before appending `assistant_message`, guard against duplicate append behavior by appending it once when handling tool requests:

```python
            messages.append(assistant_message)
```

Then remove any second append of the same message inside the blocked branch if present.

- [ ] **Step 4: Run tests and compile verification**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
python3 -m compileall tradeharness tests
```

Expected: tests pass and the runtime compiles without syntax errors.

### Task 4: Update docs and verify the dry-run runtime behavior

**Files:**
- Modify: `TradeHarness/README.MD`

- [ ] **Step 1: Document the action-realization layer**

Add this section below `## Procedural Skill Layer` in `README.MD`:

```md
## Action Realization Layer

The runtime includes a deterministic action-realization gate for execution tools.

- it checks state validity before execution tools are allowed through
- it blocks invalid entry or close actions before they reach Binance
- it feeds block feedback back to the LLM so the model can self-correct
- it enforces a small retry limit to prevent infinite correction loops

This first phase validates position-aware and inspection-aware state only.
```

- [ ] **Step 2: Run the dry-run agent cycle**

Run:

```bash
cd /Users/atif/Public/TradeHarness
DRY_RUN=true python3 - <<'PY'
from tradeharness.main import run_once
run_once()
PY
```

Expected:

- the runtime still prints observation `tool=` lines
- if an invalid execution tool is attempted, it prints an `action_realization=BLOCK` line and re-prompts
- no real order is submitted
- the loop either reaches a valid final answer or stops at the retry limit

- [ ] **Step 3: Commit**

```bash
git add README.MD tradeharness/runtime/action_realization tradeharness/runtime/agent.py tests/test_agent_tools.py
git commit -m "feat: add action realization layer"
```

## Self-Review

- Spec coverage check:
  - deterministic gate module: covered by Task 1
  - position-aware and inspection-aware checks: covered by Task 1
  - block feedback to LLM: covered by Task 2
  - retry limit: covered by Task 2
  - runtime safe re-prompt flow: covered by Task 3
  - dry-run verification: covered by Task 4
- Placeholder scan: no `TODO`, `TBD`, or vague implementation markers remain.
- Type consistency: `realize_action`, `EXECUTION_TOOL_NAMES`, `MAX_ACTION_REALIZATION_RETRIES`, and `build_action_block_feedback` are named consistently across tasks.
