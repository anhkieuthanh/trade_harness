# Trajectory Regulation Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first trajectory-regulation layer so the runtime can detect repetition, stagnation, and budget exhaustion, then warn or stop the agent before the cycle degenerates.

**Architecture:** Introduce a lightweight deterministic monitor under `runtime/trajectory_regulation` that evaluates compact trajectory history from the current cycle. The runtime will record tool-level and turn-level events, ask the monitor for an `ALLOW/WARN/STOP` decision, inject warnings back into the conversation when appropriate, and terminate the cycle with a forced summary on hard-stop conditions.

**Tech Stack:** Python 3, `unittest`, `compileall`, existing `tradeharness` runtime architecture

---

## File Structure

- Create: `TradeHarness/tradeharness/runtime/trajectory_regulation/__init__.py`
- Create: `TradeHarness/tradeharness/runtime/trajectory_regulation/monitor.py`
- Modify: `TradeHarness/tradeharness/runtime/agent.py`
- Modify: `TradeHarness/tests/test_agent_tools.py`
- Modify: `TradeHarness/README.MD`

## Implementation Notes

- Keep the first version deterministic and local to one cycle.
- Use compact history records instead of transcript-wide semantic parsing.
- Soft warnings should append guidance to the LLM conversation.
- Hard stops should terminate the cycle with a forced final summary.
- Observation tools and blocked actions should both contribute to history because both can indicate degeneration.

### Task 1: Add the trajectory monitor and verify its `ALLOW/WARN/STOP` heuristics

**Files:**
- Create: `TradeHarness/tradeharness/runtime/trajectory_regulation/__init__.py`
- Create: `TradeHarness/tradeharness/runtime/trajectory_regulation/monitor.py`
- Test: `TradeHarness/tests/test_agent_tools.py`

- [ ] **Step 1: Write the failing trajectory-monitor tests**

Append these tests to `tests/test_agent_tools.py`:

```python
from tradeharness.runtime.trajectory_regulation.monitor import regulate_trajectory


class TrajectoryRegulationTests(unittest.TestCase):
    def test_warns_on_repeated_same_tool_pattern(self) -> None:
        result = regulate_trajectory(
            history=[
                {"event": "tool", "tool_name": "get_balance", "blocked": False},
                {"event": "tool", "tool_name": "get_balance", "blocked": False},
                {"event": "tool", "tool_name": "get_balance", "blocked": False},
            ],
            steps_remaining=4,
            final_answer_present=False,
        )

        self.assertEqual(result["decision"], "WARN")
        self.assertIn("repeating", result["reason"].lower())

    def test_stops_on_repeated_same_block_reason(self) -> None:
        result = regulate_trajectory(
            history=[
                {
                    "event": "block",
                    "tool_name": "open_long",
                    "block_reason": "No open position is available to close.",
                },
                {
                    "event": "block",
                    "tool_name": "open_long",
                    "block_reason": "No open position is available to close.",
                },
                {
                    "event": "block",
                    "tool_name": "open_long",
                    "block_reason": "No open position is available to close.",
                },
            ],
            steps_remaining=4,
            final_answer_present=False,
        )

        self.assertEqual(result["decision"], "STOP")
        self.assertIn("block", result["reason"].lower())

    def test_warns_when_budget_is_low_without_final_answer(self) -> None:
        result = regulate_trajectory(
            history=[{"event": "tool", "tool_name": "get_market_snapshot", "blocked": False}],
            steps_remaining=1,
            final_answer_present=False,
        )

        self.assertEqual(result["decision"], "WARN")
        self.assertIn("budget", result["reason"].lower())

    def test_allows_healthy_short_trajectory(self) -> None:
        result = regulate_trajectory(
            history=[
                {"event": "tool", "tool_name": "get_market_snapshot", "blocked": False},
                {"event": "tool", "tool_name": "get_position", "blocked": False},
            ],
            steps_remaining=5,
            final_answer_present=False,
        )

        self.assertEqual(result["decision"], "ALLOW")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: `ModuleNotFoundError` for `tradeharness.runtime.trajectory_regulation.monitor`.

- [ ] **Step 3: Create the package marker**

Create `tradeharness/runtime/trajectory_regulation/__init__.py`:

```python
from tradeharness.runtime.trajectory_regulation.monitor import regulate_trajectory

__all__ = ["regulate_trajectory"]
```

- [ ] **Step 4: Implement the deterministic trajectory monitor**

Create `tradeharness/runtime/trajectory_regulation/monitor.py`:

```python
from __future__ import annotations

from collections import Counter
from typing import Any


def regulate_trajectory(
    *,
    history: list[dict[str, Any]],
    steps_remaining: int,
    final_answer_present: bool,
) -> dict[str, Any]:
    if final_answer_present:
        return {
            "decision": "ALLOW",
            "reason": "Final answer already present.",
            "details": {},
        }

    recent_tools = [item["tool_name"] for item in history if item.get("event") == "tool"]
    if len(recent_tools) >= 3 and len(set(recent_tools[-3:])) == 1:
        return {
            "decision": "WARN",
            "reason": f"Agent is repeating the same tool too often: {recent_tools[-1]}",
            "details": {"tool_name": recent_tools[-1]},
        }

    block_reasons = [
        item["block_reason"]
        for item in history
        if item.get("event") == "block" and item.get("block_reason")
    ]
    repeated_blocks = Counter(block_reasons)
    for reason, count in repeated_blocks.items():
        if count >= 3:
            return {
                "decision": "STOP",
                "reason": f"Repeated blocked action detected: {reason}",
                "details": {"block_reason": reason, "count": count},
            }

    observation_only_events = [
        item
        for item in history[-5:]
        if item.get("event") == "tool"
        and item.get("tool_name") in {"get_market_snapshot", "get_position", "get_balance"}
    ]
    if len(observation_only_events) >= 5:
        return {
            "decision": "WARN",
            "reason": "Trajectory appears stagnant: repeated observation without clear progress.",
            "details": {"window_size": len(observation_only_events)},
        }

    if steps_remaining <= 1:
        return {
            "decision": "WARN",
            "reason": "Budget is nearly exhausted; conclude now or return a no-trade summary.",
            "details": {"steps_remaining": steps_remaining},
        }

    return {
        "decision": "ALLOW",
        "reason": "Trajectory is currently healthy.",
        "details": {},
    }
```

- [ ] **Step 5: Run tests to verify monitor heuristics pass**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: the new trajectory tests pass, or any remaining failures point only to runtime integration work.

### Task 2: Add runtime helpers for trajectory warnings and hard-stop summaries

**Files:**
- Modify: `TradeHarness/tradeharness/runtime/agent.py`
- Test: `TradeHarness/tests/test_agent_tools.py`

- [ ] **Step 1: Write the failing runtime helper tests**

Append these tests to `tests/test_agent_tools.py`:

```python
from tradeharness.runtime.agent import (
    build_trajectory_stop_summary,
    build_trajectory_warning_feedback,
)


class TrajectoryRuntimeHelpersTests(unittest.TestCase):
    def test_build_trajectory_warning_feedback_contains_reason(self) -> None:
        feedback = build_trajectory_warning_feedback(
            {
                "decision": "WARN",
                "reason": "Agent is repeating the same tool too often: get_balance",
                "details": {},
            }
        )

        self.assertIn("Trajectory warning", feedback)
        self.assertIn("get_balance", feedback)

    def test_build_trajectory_stop_summary_contains_reason(self) -> None:
        summary = build_trajectory_stop_summary(
            {
                "decision": "STOP",
                "reason": "Repeated blocked action detected: same invalid close request",
                "details": {},
            }
        )

        self.assertIn("trajectory_regulation_stop", summary)
        self.assertIn("Repeated blocked action detected", summary)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: failure because the new helper functions do not exist yet.

- [ ] **Step 3: Import the monitor into the runtime**

Add this import to `tradeharness/runtime/agent.py`:

```python
from tradeharness.runtime.trajectory_regulation.monitor import regulate_trajectory
```

- [ ] **Step 4: Add warning and stop summary helpers**

Add these functions to `tradeharness/runtime/agent.py` above `run_agent_cycle(...)`:

```python
def build_trajectory_warning_feedback(regulation_result: dict[str, Any]) -> str:
    return (
        "Trajectory warning from Trajectory Regulation Layer. "
        f"Reason: {regulation_result['reason']} "
        "Adjust your behavior, avoid repeating the same failed pattern, and either progress or conclude."
    )


def build_trajectory_stop_summary(regulation_result: dict[str, Any]) -> str:
    return json.dumps(
        {
            "final": "trajectory_regulation_stop",
            "reason": regulation_result["reason"],
        }
    )
```

- [ ] **Step 5: Run tests to verify the helpers pass**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: helper tests pass with no regressions.

### Task 3: Wire compact trajectory history and regulation decisions into the runtime loop

**Files:**
- Modify: `TradeHarness/tradeharness/runtime/agent.py`

- [ ] **Step 1: Initialize compact trajectory history**

Inside `run_agent_cycle(settings: Settings)`, after `blocked_attempts = 0`, add:

```python
    trajectory_history: list[dict[str, Any]] = []
```

- [ ] **Step 2: Record tool-level and block-level events**

Inside the tool-request loop:

When the gate returns `BLOCK`, append:

```python
                    trajectory_history.append(
                        {
                            "event": "block",
                            "tool_name": tool_request.name,
                            "block_reason": gate_result["reason"],
                        }
                    )
```

When a tool executes successfully, append:

```python
                trajectory_history.append(
                    {
                        "event": "tool",
                        "tool_name": tool_request.name,
                        "blocked": False,
                    }
                )
```

- [ ] **Step 3: Regulate after tool-level updates**

After each appended trajectory event, call:

```python
                regulation_result = regulate_trajectory(
                    history=trajectory_history,
                    steps_remaining=6 - _ - 1,
                    final_answer_present=False,
                )
```

If `regulation_result["decision"] == "WARN"`:

```python
                    messages.append(
                        {
                            "role": "user",
                            "content": build_trajectory_warning_feedback(regulation_result),
                        }
                    )
                    print(f"trajectory_regulation=WARN result={json.dumps(regulation_result)}")
                    break
```

If `regulation_result["decision"] == "STOP"`:

```python
                    print(f"trajectory_regulation=STOP result={json.dumps(regulation_result)}")
                    print(f"agent={build_trajectory_stop_summary(regulation_result)}")
                    return
```

- [ ] **Step 4: Regulate at turn-level for budget exhaustion**

Near the end of the `for _ in range(6):` loop, before the next turn begins, add a turn-level budget check:

```python
        regulation_result = regulate_trajectory(
            history=trajectory_history,
            steps_remaining=6 - _ - 1,
            final_answer_present=bool(content),
        )
        if regulation_result["decision"] == "STOP":
            print(f"trajectory_regulation=STOP result={json.dumps(regulation_result)}")
            print(f"agent={build_trajectory_stop_summary(regulation_result)}")
            return
```

- [ ] **Step 5: Ensure warning-driven `break` restarts the next LLM turn**

Use a flag such as:

```python
            trajectory_warning_in_this_turn = False
```

Set it when a warning is injected, and after the per-tool loop:

```python
            if trajectory_warning_in_this_turn:
                continue
```

This preserves safe re-prompt behavior.

- [ ] **Step 6: Run tests and compile verification**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
python3 -m compileall tradeharness tests
```

Expected: tests pass and the runtime compiles without syntax errors.

### Task 4: Update docs and verify dry-run regulation behavior

**Files:**
- Modify: `TradeHarness/README.MD`

- [ ] **Step 1: Document the trajectory regulation layer**

Add this section below `## Action Realization Layer` in `README.MD`:

```md
## Trajectory Regulation Layer

The runtime includes a trajectory-regulation layer that supervises the health of the full agent loop.

- it monitors repetition, stagnation, and budget exhaustion
- it can issue soft warnings back to the LLM
- it can hard-stop the cycle when the trajectory becomes too unhealthy
- it uses compact per-cycle history rather than a cross-session store

This first phase is deterministic and local to the current runtime cycle.
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

- the runtime still prints `tool=` lines
- if the trajectory degenerates, it prints `trajectory_regulation=WARN` or `trajectory_regulation=STOP`
- no real order is submitted
- the cycle still ends with a final summary

- [ ] **Step 3: Commit**

```bash
git add README.MD tradeharness/runtime/trajectory_regulation tradeharness/runtime/agent.py tests/test_agent_tools.py
git commit -m "feat: add trajectory regulation layer"
```

## Self-Review

- Spec coverage check:
  - trajectory monitor: covered by Task 1
  - repetition, stagnation, and budget heuristics: covered by Task 1
  - warn/stop helpers: covered by Task 2
  - tool-level and turn-level runtime wiring: covered by Task 3
  - dry-run verification: covered by Task 4
- Placeholder scan: no `TODO`, `TBD`, or vague implementation markers remain.
- Type consistency: `regulate_trajectory`, `build_trajectory_warning_feedback`, and `build_trajectory_stop_summary` are named consistently across tasks.
