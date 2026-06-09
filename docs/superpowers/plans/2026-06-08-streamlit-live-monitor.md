# Streamlit Live Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `streamlit_app.py` into a single-page operator console for live monitoring, evolution visibility, and safe operational controls.

**Architecture:** Extend the existing Streamlit app instead of replacing it. Keep the app single-page, add deterministic data loaders for runtime and evolution artifacts, then layer in safe operator controls that can trigger offline evolution without exposing direct trading actions.

**Tech Stack:** Python, Streamlit, existing TradeHarness runtime/evolution artifacts, `subprocess`, `pathlib`, `json`

---

### Task 1: Refactor Dashboard Data Loaders

**Files:**
- Modify: `streamlit_app.py`
- Test: `tests/test_streamlit_dashboard.py`

- [ ] **Step 1: Write the failing tests for settings and artifact loading**

```python
from pathlib import Path

from streamlit_app import (
    load_env_settings,
    load_harness_meta,
    load_latest_evolution_snapshot,
)


def test_load_harness_meta_prefers_artifact_values(tmp_path: Path) -> None:
    meta_path = tmp_path / "harness_meta.json"
    meta_path.write_text('{"harness_version":"v3"}', encoding="utf-8")

    payload = load_harness_meta(meta_path)

    assert payload["harness_version"] == "v3"


def test_load_latest_evolution_snapshot_handles_missing_files(tmp_path: Path) -> None:
    snapshot = load_latest_evolution_snapshot(tmp_path)

    assert snapshot.daily_report_text == ""
    assert snapshot.pass_metrics == {}
    assert snapshot.annotations_count == 0
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_streamlit_dashboard -v`  
Expected: FAIL because the new helper functions and test module do not exist yet.

- [ ] **Step 3: Add focused dashboard artifact helpers**

```python
@dataclass
class EvolutionSnapshot:
    daily_report_path: Path | None
    daily_report_text: str
    pass_metrics: dict[str, Any]
    annotations_count: int
    candidates_count: int
    regression_notes_count: int
    harness_meta: dict[str, Any]


def load_harness_meta(meta_path: Path) -> dict[str, Any]:
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def load_latest_evolution_snapshot(evolution_dir: Path) -> EvolutionSnapshot:
    ...
```

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_streamlit_dashboard -v`  
Expected: PASS.

- [ ] **Step 5: Commit the loader refactor**

```bash
git add streamlit_app.py tests/test_streamlit_dashboard.py
git commit -m "feat: add streamlit dashboard data loaders"
```

### Task 2: Add Runtime Metrics and Header Context

**Files:**
- Modify: `streamlit_app.py`
- Test: `tests/test_streamlit_dashboard.py`

- [ ] **Step 1: Write the failing tests for recent Pass@1 and header context**

```python
from streamlit_app import compute_recent_pass_at_1, build_header_context


def test_compute_recent_pass_at_1_uses_recent_window() -> None:
    episodes = [
        {"final_status": "SUCCESS"},
        {"final_status": "FAILED"},
        {"final_status": "SUCCESS"},
    ]

    value = compute_recent_pass_at_1(episodes, window=3)

    assert value == 2 / 3


def test_build_header_context_uses_harness_meta_version() -> None:
    context = build_header_context(
        env_settings={"TASK_ID": "task-a"},
        harness_meta={"harness_version": "v9"},
    )

    assert context["harness_version"] == "v9"
    assert context["task_id"] == "task-a"
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_streamlit_dashboard -v`  
Expected: FAIL because the metric and header helpers do not exist yet.

- [ ] **Step 3: Implement recent Pass@1 and header helpers in the app**

```python
def compute_recent_pass_at_1(episodes: list[EpisodeSummary], window: int = 20) -> float:
    recent = episodes[-window:]
    if not recent:
        return 0.0
    passed = sum(1 for episode in recent if episode.final_status == "SUCCESS")
    return passed / len(recent)


def build_header_context(
    *,
    env_settings: dict[str, str],
    harness_meta: dict[str, Any],
) -> dict[str, str]:
    return {
        "harness_version": str(
            harness_meta.get("harness_version")
            or env_settings.get("HARNESS_VERSION", "local")
        ),
        "task_id": env_settings.get("TASK_ID", "unknown"),
    }
```

- [ ] **Step 4: Update `render_header` to show harness version, task id, and manual refresh**

```python
def render_header(state: DashboardState, header_context: dict[str, str]) -> None:
    st.title("TradeHarness Live Operator Console")
    st.caption("Single-page operator view for runtime and evolution monitoring")
    ...
    st.metric("Harness version", header_context["harness_version"])
    st.metric("Task", header_context["task_id"])
    if st.button("Refresh now", use_container_width=True):
        st.rerun()
```

- [ ] **Step 5: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_streamlit_dashboard -v`  
Expected: PASS.

- [ ] **Step 6: Commit the runtime metrics update**

```bash
git add streamlit_app.py tests/test_streamlit_dashboard.py
git commit -m "feat: add streamlit runtime metrics and header context"
```

### Task 3: Add Latest Episode Step View and Evolution Summary

**Files:**
- Modify: `streamlit_app.py`
- Test: `tests/test_streamlit_dashboard.py`

- [ ] **Step 1: Write the failing tests for latest-step preview and evolution summary parsing**

```python
from streamlit_app import summarize_latest_steps, load_latest_evolution_snapshot


def test_summarize_latest_steps_returns_compact_rows() -> None:
    rows = summarize_latest_steps(
        {
            "steps": [
                {
                    "step_index": 1,
                    "action": {"tool": "get_balance"},
                    "harness_intervention": {"decision": "EXECUTE"},
                    "environment_feedback": {"asset": "USDT"},
                }
            ]
        }
    )

    assert rows[0]["step_index"] == 1
    assert rows[0]["action"] == "get_balance"
    assert rows[0]["decision"] == "EXECUTE"
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_streamlit_dashboard -v`  
Expected: FAIL because the helper does not exist yet.

- [ ] **Step 3: Add compact latest-step and evolution preview helpers**

```python
def summarize_latest_steps(raw_episode: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for step in raw_episode.get("steps", []):
        action = step.get("action", {})
        rows.append(
            {
                "step_index": step.get("step_index", "—"),
                "action": str(action.get("tool") or "final_response"),
                "decision": str(
                    step.get("harness_intervention", {}).get("decision", "unknown")
                ),
                "feedback": json.dumps(
                    step.get("environment_feedback", {}),
                    ensure_ascii=True,
                )[:160],
            }
        )
    return rows
```

- [ ] **Step 4: Render an evolution summary block in the page**

```python
def render_evolution_summary(snapshot: EvolutionSnapshot) -> None:
    st.subheader("Harness and evolution summary")
    st.markdown(f"- **Latest promoted version:** {snapshot.harness_meta.get('harness_version', '—')}")
    st.markdown(f"- **Annotations:** {snapshot.annotations_count}")
    st.markdown(f"- **Candidates:** {snapshot.candidates_count}")
    st.markdown(f"- **Regression notes:** {snapshot.regression_notes_count}")
    if snapshot.daily_report_text:
        st.code(snapshot.daily_report_text[:2000], language="markdown")
```

- [ ] **Step 5: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_streamlit_dashboard -v`  
Expected: PASS.

- [ ] **Step 6: Commit the latest-episode and evolution summary UI**

```bash
git add streamlit_app.py tests/test_streamlit_dashboard.py
git commit -m "feat: add streamlit episode and evolution summary views"
```

### Task 4: Add Safe Operator Controls

**Files:**
- Modify: `streamlit_app.py`
- Test: `tests/test_streamlit_dashboard.py`

- [ ] **Step 1: Write the failing tests for safe command execution helpers**

```python
from streamlit_app import build_offline_evolution_command, run_safe_command


def test_build_offline_evolution_command_points_to_module() -> None:
    command = build_offline_evolution_command()

    assert command == ["python3", "-m", "tradeharness.evolution.main"]


def test_run_safe_command_captures_exit_code() -> None:
    result = run_safe_command(["python3", "-c", "print('ok')"])

    assert result["returncode"] == 0
    assert "ok" in result["stdout"]
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `python3 -m unittest tests.test_streamlit_dashboard -v`  
Expected: FAIL because the command helpers do not exist yet.

- [ ] **Step 3: Implement safe ops helpers**

```python
def build_offline_evolution_command() -> list[str]:
    return ["python3", "-m", "tradeharness.evolution.main"]


def run_safe_command(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
```

- [ ] **Step 4: Add safe ops UI with manual actions only**

```python
def render_safe_ops() -> None:
    st.subheader("Safe operator controls")
    if st.button("Run offline evolution now", use_container_width=True):
        result = run_safe_command(build_offline_evolution_command())
        if result["returncode"] == 0:
            st.success("Offline evolution completed.")
        else:
            st.error("Offline evolution failed.")
        st.code(result["stdout"] or result["stderr"], language="text")
```

- [ ] **Step 5: Run the targeted tests to verify they pass**

Run: `python3 -m unittest tests.test_streamlit_dashboard -v`  
Expected: PASS.

- [ ] **Step 6: Commit the safe ops controls**

```bash
git add streamlit_app.py tests/test_streamlit_dashboard.py
git commit -m "feat: add streamlit safe operator controls"
```

### Task 5: Update Wiring, Docs, and Final Verification

**Files:**
- Modify: `streamlit_app.py`
- Modify: `README.MD`
- Test: `tests/test_streamlit_dashboard.py`

- [ ] **Step 1: Wire the new helpers into `main()`**

```python
def main() -> None:
    st.set_page_config(page_title="TradeHarness Monitor", layout="wide")
    ...
    env_settings = load_env_settings(str(DEFAULT_ENV_PATH))
    evolution_snapshot = load_latest_evolution_snapshot(REPO_ROOT / "var" / "evolution")
    header_context = build_header_context(
        env_settings=env_settings,
        harness_meta=evolution_snapshot.harness_meta,
    )
    state = build_state(Path(log_path_input), env_settings)
    render_header(state, header_context)
    render_latest_cycle(state)
    render_recent_activity(state)
    render_evolution_summary(evolution_snapshot)
    render_safe_ops()
    render_raw_view(state)
```

- [ ] **Step 2: Update README with the Streamlit monitor run command**

```md
## Streamlit Monitor

Run the local operator console with:

```bash
cd /Users/atif/Public/TradeHarness
streamlit run streamlit_app.py
```

The page shows runtime health, recent episodes, evolution artifacts, and a safe button to trigger offline evolution manually.
```

- [ ] **Step 3: Run the full dashboard-related test suite**

Run: `python3 -m unittest tests.test_streamlit_dashboard tests.test_offline_evolution -v`  
Expected: PASS.

- [ ] **Step 4: Run broader regression checks**

Run: `python3 -m unittest tests.test_agent_tools -v`  
Expected: PASS.

- [ ] **Step 5: Run compile verification**

Run: `python3 -m compileall tradeharness tests streamlit_app.py`  
Expected: completes without syntax errors.

- [ ] **Step 6: Commit the final integrated operator console**

```bash
git add streamlit_app.py README.MD tests/test_streamlit_dashboard.py
git commit -m "feat: upgrade streamlit live operator console"
```
