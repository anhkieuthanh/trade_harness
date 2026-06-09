from __future__ import annotations

import json
import os
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from tradeharness.control.state import (
    ControlState,
    RiskControlState,
    StrategyControlState,
    load_control_state,
    save_control_state,
)
from tradeharness.evolution.metrics import compute_pass_at_1

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_LOG_PATH = REPO_ROOT / "var" / "trajectories" / "episodes.jsonl"
DEFAULT_ENV_PATH = REPO_ROOT / ".env"
DEFAULT_EVOLUTION_DIR = REPO_ROOT / "var" / "evolution"
DEFAULT_CONTROL_STATE_PATH = REPO_ROOT / "var" / "control" / "state.json"
DEFAULT_HARNESS_META_PATH = (
    REPO_ROOT / "tradeharness" / "evolution" / "artifacts" / "current" / "harness_meta.json"
)


@dataclass
class EpisodeSummary:
    episode_id: str
    started_at: datetime | None
    ended_at: datetime | None
    final_status: str
    termination_reason: str
    mode: str
    symbol: str
    step_count: int
    latest_tool: str
    latest_result: str
    harness_decision: str
    raw: dict[str, Any]


@dataclass
class DashboardState:
    log_path: Path
    episodes: list[EpisodeSummary]
    symbol: str
    mode: str
    poll_interval_seconds: int | None
    latest_ended_at: datetime | None
    age_seconds: int | None
    is_alive: bool
    stale_after_seconds: int
    latest: EpisodeSummary | None
    recent_status_counts: Counter
    recent_decision_counts: Counter


@dataclass
class EvolutionSnapshot:
    daily_report_path: Path | None
    daily_report_text: str
    pass_metrics: dict[str, Any]
    annotations_count: int
    candidates_count: int
    regression_notes_count: int
    harness_meta: dict[str, Any]


def parse_iso(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_env_settings(env_path_str: str, refresh_nonce: int = 0) -> dict[str, str]:
    env_path = Path(env_path_str)
    data: dict[str, str] = {}
    if not env_path.exists():
        return data
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def load_episode_summaries(
    log_path_str: str,
    limit: int = 300,
    refresh_nonce: int = 0,
) -> list[EpisodeSummary]:
    log_path = Path(log_path_str)
    if not log_path.exists():
        return []

    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    summaries: list[EpisodeSummary] = []
    for raw in lines[-limit:]:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        steps = payload.get("steps") or []
        last_step = steps[-1] if steps else {}
        action = last_step.get("action") if isinstance(last_step, dict) else {}
        harness = last_step.get("harness_intervention") if isinstance(last_step, dict) else {}
        latest_tool = "—"
        latest_result = payload.get("final_status") or "unknown"
        if isinstance(action, dict):
            if action.get("tool"):
                latest_tool = str(action.get("tool"))
            elif action.get("final_response"):
                latest_tool = "final_response"
        env_feedback = last_step.get("environment_feedback") if isinstance(last_step, dict) else {}
        if isinstance(env_feedback, dict):
            emitted = env_feedback.get("emitted")
            if isinstance(emitted, dict):
                latest_result = str(emitted.get("status") or emitted.get("result") or latest_result)

        summaries.append(
            EpisodeSummary(
                episode_id=str(payload.get("episode_id", "")),
                started_at=parse_iso(payload.get("started_at")),
                ended_at=parse_iso(payload.get("ended_at")),
                final_status=str(payload.get("final_status", "unknown")),
                termination_reason=str(payload.get("termination_reason", "unknown")),
                mode=str(payload.get("mode", "unknown")),
                symbol=str(payload.get("symbol", "unknown")),
                step_count=len(steps),
                latest_tool=latest_tool,
                latest_result=latest_result,
                harness_decision=str(harness.get("decision", "unknown")) if isinstance(harness, dict) else "unknown",
                raw=payload,
            )
        )
    return summaries


def load_harness_meta(meta_path: Path, refresh_nonce: int = 0) -> dict[str, Any]:
    if not meta_path.exists():
        return {}
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_json_list(path: Path) -> list[Any]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def load_latest_evolution_snapshot(
    evolution_dir: Path,
    harness_meta_path: Path | None = None,
    refresh_nonce: int = 0,
) -> EvolutionSnapshot:
    daily_report_path = evolution_dir / "daily-report.md"
    pass_metrics_path = evolution_dir / "pass-metrics.json"
    annotations_path = evolution_dir / "annotations.json"
    candidates_path = evolution_dir / "candidates.json"
    regression_notes_path = evolution_dir / "regression-notes.json"
    meta_path = harness_meta_path or evolution_dir / "harness_meta.json"

    if daily_report_path.exists():
        try:
            daily_report_text = daily_report_path.read_text(encoding="utf-8")
        except OSError:
            daily_report_text = ""
    else:
        daily_report_text = ""

    return EvolutionSnapshot(
        daily_report_path=daily_report_path if daily_report_path.exists() else None,
        daily_report_text=daily_report_text,
        pass_metrics=_load_json_dict(pass_metrics_path),
        annotations_count=len(_load_json_list(annotations_path)),
        candidates_count=len(_load_json_list(candidates_path)),
        regression_notes_count=len(_load_json_list(regression_notes_path)),
        harness_meta=load_harness_meta(meta_path, refresh_nonce=refresh_nonce),
    )


def _resolve_repo_relative_path(repo_root: Path, configured_path: str, fallback: Path) -> Path:
    raw = configured_path.strip()
    if not raw:
        return fallback
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate

def _refresh_state_key(section: str) -> str:
    return f"{section}_refresh_nonce"


def get_refresh_nonce(section: str) -> int:
    value = st.session_state.get(_refresh_state_key(section), 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def bump_refresh_nonce(section: str) -> int:
    next_value = get_refresh_nonce(section) + 1
    st.session_state[_refresh_state_key(section)] = next_value
    return next_value


def resolve_dashboard_paths(log_path: Path) -> dict[str, Path]:
    selected_log_path = log_path.expanduser()
    if not selected_log_path.is_absolute():
        selected_log_path = (REPO_ROOT / selected_log_path).resolve(strict=False)

    repo_root = REPO_ROOT
    for candidate in [selected_log_path.parent, *selected_log_path.parents]:
        env_candidate = candidate / ".env"
        meta_candidate = candidate / "tradeharness" / "evolution" / "artifacts" / "current" / "harness_meta.json"
        evolution_candidate = candidate / "var" / "evolution"
        if env_candidate.exists() or meta_candidate.exists() or evolution_candidate.exists():
            repo_root = candidate
            break

    env_path = repo_root / ".env"
    env_settings = load_env_settings(str(env_path))
    evolution_dir = _resolve_repo_relative_path(
        repo_root,
        env_settings.get("EVOLUTION_OUTPUT_DIR", ""),
        repo_root / "var" / "evolution",
    )
    harness_meta_path = _resolve_repo_relative_path(
        repo_root,
        env_settings.get("ACTIVE_HARNESS_META_ARTIFACT_PATH", ""),
        repo_root / "tradeharness" / "evolution" / "artifacts" / "current" / "harness_meta.json",
    )
    control_state_path = _resolve_repo_relative_path(
        repo_root,
        env_settings.get("CONTROL_STATE_PATH", ""),
        repo_root / "var" / "control" / "state.json",
    )
    return {
        "repo_root": repo_root,
        "log_path": selected_log_path,
        "env_path": env_path,
        "evolution_dir": evolution_dir,
        "harness_meta_path": harness_meta_path,
        "control_state_path": control_state_path,
    }


def build_state(log_path: Path, env_settings: dict[str, str]) -> DashboardState:
    episodes = load_episode_summaries(str(log_path))
    latest = episodes[-1] if episodes else None
    symbol = latest.symbol if latest else env_settings.get("SYMBOL", "BTCUSDT")
    mode = latest.mode if latest else ("dry_run" if env_settings.get("DRY_RUN", "true").lower() in {"1", "true", "yes", "on"} else "live")
    poll_interval = None
    if env_settings.get("POLL_INTERVAL_SECONDS"):
        try:
            poll_interval = int(env_settings["POLL_INTERVAL_SECONDS"])
        except ValueError:
            poll_interval = None
    stale_after_seconds = max((poll_interval or 30) * 3, 90)
    latest_ended_at = latest.ended_at if latest else None
    age_seconds = None
    is_alive = False
    if latest_ended_at:
        age_seconds = int((datetime.now(timezone.utc) - latest_ended_at.astimezone(timezone.utc)).total_seconds())
        is_alive = age_seconds <= stale_after_seconds
    recent_status_counts = Counter(ep.final_status for ep in episodes[-20:])
    recent_decision_counts = Counter(ep.harness_decision for ep in episodes[-20:])
    return DashboardState(
        log_path=log_path,
        episodes=episodes,
        symbol=symbol,
        mode=mode,
        poll_interval_seconds=poll_interval,
        latest_ended_at=latest_ended_at,
        age_seconds=age_seconds,
        is_alive=is_alive,
        stale_after_seconds=stale_after_seconds,
        latest=latest,
        recent_status_counts=recent_status_counts,
        recent_decision_counts=recent_decision_counts,
    )


def compute_recent_pass_at_1(
    episodes: list[EpisodeSummary | dict[str, Any]],
    window: int = 20,
) -> float:
    recent = episodes[-window:]
    if not recent:
        return 0.0

    serialized_recent = [
        episode.raw if isinstance(episode, EpisodeSummary) else episode
        for episode in recent
    ]
    return float(compute_pass_at_1(serialized_recent)["pass_at_1"])


def build_header_context(
    *,
    env_settings: dict[str, str],
    harness_meta: dict[str, Any],
) -> dict[str, str]:
    return {
        "harness_version": str(
            harness_meta.get("harness_version")
            or env_settings.get("HARNESS_VERSION")
            or "local"
        ),
        "task_id": str(env_settings.get("TASK_ID") or "unknown"),
    }


def summarize_latest_steps(raw_episode: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    steps = raw_episode.get("steps", [])
    if not isinstance(steps, list):
        return []

    rows: list[dict[str, Any]] = []
    for step in steps[-limit:]:
        if not isinstance(step, dict):
            continue
        action = step.get("action", {})
        action_name = "unknown_action"
        if isinstance(action, dict):
            if action.get("tool"):
                action_name = str(action["tool"])
            elif action.get("final_response"):
                action_name = "final_response"
        else:
            action_name = "malformed_action"
        feedback = step.get("environment_feedback", {})
        if not isinstance(feedback, dict):
            feedback = {}
        harness = step.get("harness_intervention", {})
        rows.append(
            {
                "step_index": step.get("step_index", "—"),
                "action": action_name,
                "decision": str(harness.get("decision", "unknown")) if isinstance(harness, dict) else "unknown",
                "feedback": json.dumps(feedback, ensure_ascii=True)[:160],
            }
        )
    return rows


def _format_pass_at_1(value: Any) -> str:
    try:
        if value is None:
            return "—"
        return f"{float(value):.0%}"
    except (TypeError, ValueError):
        return "—"


def build_evolution_summary_rows(snapshot: EvolutionSnapshot) -> list[dict[str, str]]:
    rows = [
        {
            "label": "Latest promoted version",
            "value": str(snapshot.harness_meta.get("harness_version") or "—"),
        },
        {
            "label": "Pass@1",
            "value": _format_pass_at_1(snapshot.pass_metrics.get("pass_at_1")),
        },
        {
            "label": "Pass window",
            "value": str(snapshot.pass_metrics.get("recent_window") or snapshot.pass_metrics.get("window") or "—"),
        },
        {"label": "Annotations", "value": str(snapshot.annotations_count)},
        {"label": "Candidates", "value": str(snapshot.candidates_count)},
        {"label": "Regression notes", "value": str(snapshot.regression_notes_count)},
    ]
    if snapshot.daily_report_text:
        rows.append(
            {
                "label": "Daily report",
                "value": snapshot.daily_report_text[:2000],
            }
        )
    return rows


def build_offline_evolution_command() -> list[str]:
    return ["python3", "-m", "tradeharness.evolution.main"]


def run_safe_command(command: list[str], timeout_seconds: int = 300) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": f"Command timed out after {timeout_seconds} seconds.",
        }
    except TimeoutError as exc:
        return {
            "returncode": 124,
            "stdout": "",
            "stderr": f"Command timed out after {timeout_seconds} seconds: {exc}",
        }
    except Exception as exc:
        return {
            "returncode": 1,
            "stdout": "",
            "stderr": f"Command failed before completion: {exc}",
        }
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }

def _parse_control_time(value: str) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        return time(hour=1, minute=0)

def _format_control_time(value: time) -> str:
    return value.strftime("%H:%M")


def fmt_dt(value: datetime | None) -> str:
    if value is None:
        return "—"
    local = value.astimezone()
    return local.strftime("%Y-%m-%d %H:%M:%S %Z")


def fmt_age(seconds: int | None) -> str:
    if seconds is None:
        return "—"
    return str(timedelta(seconds=seconds))


def infer_operator_note(state: DashboardState) -> str:
    if not state.episodes:
        return "Chưa có episode nào. Kiểm tra daemon có đang ghi log vào trajectory file không."
    if not state.is_alive:
        return "Không thấy cycle mới đủ gần. Kiểm tra daemon / launchd / runtime blocker trước."
    latest = state.latest
    if latest is None:
        return "Chưa đủ dữ liệu để kết luận."
    if latest.final_status != "SUCCESS":
        return f"Cycle gần nhất không SUCCESS ({latest.final_status}). Mở raw payload để xem lỗi."
    if latest.latest_tool == "final_response":
        return "Cycle gần nhất chỉ đi tới inspect + final response. Nếu kỳ vọng có order, kiểm tra task/prompt/gate trước."
    if latest.harness_decision not in {"ALLOW", "EXECUTE"}:
        return f"Harness decision gần nhất là {latest.harness_decision}. Xem lại layer chặn trước khi blame market/tool."
    return "Runtime có vẻ đang sống. Theo dõi tiếp age, latest tool, và recent status để phát hiện drift."


def build_action_needed_copy(state: DashboardState) -> dict[str, str]:
    latest = state.latest
    if not state.episodes:
        return {
            "severity": "error",
            "title": "No runtime data yet",
            "body": "The daemon has not written any episode summaries. Check the live loop before trading.",
            "cta": "Check daemon",
        }
    if not state.is_alive:
        return {
            "severity": "error",
            "title": "Runtime stale",
            "body": "No fresh cycle arrived within the expected window. Inspect the daemon, launchd job, or blocked supervisor.",
            "cta": "Check daemon",
        }
    if latest is None:
        return {
            "severity": "warning",
            "title": "Latest cycle unavailable",
            "body": "We have episode history, but the latest snapshot is missing. Review the log source and payload shape.",
            "cta": "Open debug payload",
        }
    if latest.final_status in {"ERROR", "FAILED", "BLOCKED"}:
        return {
            "severity": "error",
            "title": f"Latest cycle ended {latest.final_status}",
            "body": "The last cycle did not finish cleanly. Open the latest trace and check the terminating tool or harness intervention.",
            "cta": "Review latest cycle",
        }
    if latest.harness_decision not in {"ALLOW", "EXECUTE"}:
        return {
            "severity": "warning",
            "title": "Harness is holding the cycle",
            "body": f"Latest decision was `{latest.harness_decision}`. This usually means a contract, action, or trajectory guard triggered.",
            "cta": "Review latest cycle",
        }
    if latest.latest_tool == "final_response":
        return {
            "severity": "info",
            "title": "Inspect-only cycle",
            "body": "The latest cycle stopped at inspect / final response. If you expected an order, review the task prompt and tool guidance.",
            "cta": "Open debug payload",
        }
    return {
        "severity": "success",
        "title": "Runtime healthy",
        "body": "The live loop is active and the last cycle looks consistent. Keep watching age, result, and harness decision for drift.",
        "cta": "Keep monitoring",
    }


def _severity_icon(severity: str) -> str:
    return {
        "error": "⛔",
        "warning": "⚠️",
        "success": "✅",
        "info": "ℹ️",
    }.get(severity, "ℹ️")


def render_top_bar(state: DashboardState) -> None:
    left, right = st.columns([4, 1])
    with left:
        st.title("TradeHarness Operator Console")
        st.caption("Live runtime status, controls, and offline evolution in one operator-first view.")
    with right:
        if st.button("Refresh now", use_container_width=True):
            st.rerun()
        st.caption(f"Last updated: {fmt_dt(state.latest_ended_at)}")


def render_critical_status_strip(state: DashboardState) -> None:
    latest = state.latest
    runtime_label = "ALIVE" if state.is_alive else ("STALE" if state.episodes else "EMPTY")
    latest_result = latest.latest_result if latest else "—"
    latest_decision = latest.harness_decision if latest else "—"
    strip = st.columns(6)
    strip[0].metric("Runtime", runtime_label)
    strip[1].metric("Age", fmt_age(state.age_seconds))
    strip[2].metric("Symbol", state.symbol)
    strip[3].metric("Mode", state.mode)
    strip[4].metric("Latest result", latest_result)
    strip[5].metric("Harness decision", latest_decision)


def render_action_needed_now(state: DashboardState) -> None:
    copy = build_action_needed_copy(state)
    st.markdown("### Action needed now")
    title = f"{_severity_icon(copy['severity'])} {copy['title']}"
    body = f"{copy['body']}\n\n**Next:** {copy['cta']}"
    if copy["severity"] == "error":
        st.error(body, icon="⛔")
    elif copy["severity"] == "warning":
        st.warning(body, icon="⚠️")
    elif copy["severity"] == "success":
        st.success(body, icon="✅")
    else:
        st.info(body, icon="ℹ️")
    st.caption(title)


def _operator_verdict_lines(state: DashboardState) -> list[str]:
    latest = state.latest
    verdict_lines: list[str] = []
    verdict_lines.append("runtime is active" if state.is_alive else "runtime is stale")
    if latest is None:
        verdict_lines.append("no latest cycle snapshot yet")
        return verdict_lines
    if latest.latest_tool == "final_response":
        verdict_lines.append("inspect-only cycle reached final response")
    else:
        verdict_lines.append(f"latest tool: {latest.latest_tool}")
    if latest.harness_decision in {"ALLOW", "EXECUTE"}:
        verdict_lines.append("harness let the cycle continue")
    else:
        verdict_lines.append(f"harness decision: {latest.harness_decision}")
    verdict_lines.append(
        "blocker likely in harness" if latest.harness_decision not in {"ALLOW", "EXECUTE"} else "blocker not obvious from the last cycle"
    )
    return verdict_lines[:4]


def render_current_cycle_snapshot(state: DashboardState) -> None:
    st.subheader("Current cycle snapshot")
    latest = state.latest
    if latest is None:
        st.warning("No episodes found yet.")
        return

    left, right = st.columns([1.1, 1])
    with left:
        st.markdown(
            "\n".join(
                [
                    f"- **Final status:** {latest.final_status}",
                    f"- **Termination:** {latest.termination_reason}",
                    f"- **Steps:** {latest.step_count}",
                    f"- **Latest tool/action:** {latest.latest_tool}",
                    f"- **Harness decision:** {latest.harness_decision}",
                    f"- **Started:** {fmt_dt(latest.started_at)}",
                    f"- **Ended:** {fmt_dt(latest.ended_at)}",
                ]
            )
        )
    with right:
        verdict = build_action_needed_copy(state)
        st.markdown(f"### Operator verdict")
        st.info(
            "\n".join(
                [
                    f"{_severity_icon(verdict['severity'])} {verdict['title']}",
                    *[f"- {line}" for line in _operator_verdict_lines(state)],
                ]
            )
        )

    with st.expander("Latest step trace", expanded=False):
        step_rows = summarize_latest_steps(latest.raw)
        if step_rows:
            st.dataframe(step_rows, use_container_width=True, hide_index=True)
        else:
            st.caption("No step-level trace available for this episode.")


def _style_recent_activity(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    def _row_style(row: pd.Series) -> list[str]:
        status = str(row.get("status", "")).upper()
        decision = str(row.get("decision", "")).upper()
        if status in {"ERROR", "FAILED", "BLOCKED"} or decision == "BLOCK":
            return ["background-color: rgba(185, 28, 28, 0.16)"] * len(row)
        if status in {"WARNING", "DEGRADED", "INSPECT_ONLY"} or decision in {"WARN", "HOLD"}:
            return ["background-color: rgba(180, 83, 9, 0.14)"] * len(row)
        if status == "SUCCESS" or decision in {"ALLOW", "EXECUTE"}:
            return ["background-color: rgba(21, 128, 61, 0.12)"] * len(row)
        return [""] * len(row)

    return df.style.apply(_row_style, axis=1)


def render_recent_activity(state: DashboardState) -> None:
    st.subheader("Recent activity")
    episodes = list(reversed(state.episodes[-15:]))
    rows = []
    for ep in episodes:
        rows.append(
            {
                "time": fmt_dt(ep.ended_at),
                "status": ep.final_status,
                "tool": ep.latest_tool,
                "decision": ep.harness_decision,
                "episode": ep.episode_id[:8],
                "termination": ep.termination_reason,
                "mode": ep.mode,
            }
        )
    if not rows:
        st.info("No recent activity yet.")
        return
    df = pd.DataFrame(rows)
    st.dataframe(
        _style_recent_activity(df),
        use_container_width=True,
        hide_index=True,
    )


def render_health_summary(state: DashboardState) -> None:
    st.subheader("Health summary")
    status_col, decision_col = st.columns(2)
    status_series = pd.Series(dict(state.recent_status_counts), dtype="int64")
    decision_series = pd.Series(dict(state.recent_decision_counts), dtype="int64")

    with status_col:
        st.markdown("#### Final status distribution")
        if status_series.empty:
            st.caption("No status data yet.")
        else:
            st.bar_chart(status_series.sort_values(ascending=False))
    with decision_col:
        st.markdown("#### Harness decision distribution")
        if decision_series.empty:
            st.caption("No decision data yet.")
        else:
            st.bar_chart(decision_series.sort_values(ascending=False))


def render_monitor_body(state: DashboardState, header_context: dict[str, str]) -> None:
    render_top_bar(state)
    render_critical_status_strip(state)
    render_action_needed_now(state)
    render_current_cycle_snapshot(state)
    render_recent_activity(state)
    render_health_summary(state)


def render_header(state: DashboardState, header_context: dict[str, str]) -> None:
    render_top_bar(state)
    recent_pass_at_1 = compute_recent_pass_at_1(state.episodes)
    st.caption(f"Harness version: {header_context['harness_version']} · Task: {header_context['task_id']} · Recent Pass@1: {recent_pass_at_1:.0%}")


def render_evolution_summary(snapshot: EvolutionSnapshot) -> None:
    st.subheader("Evolution")
    summary_rows = build_evolution_summary_rows(snapshot)
    summary_cols = st.columns(3)
    summary_data = [row for row in summary_rows if row["label"] != "Daily report"]
    for idx, row in enumerate(summary_data):
        with summary_cols[idx % len(summary_cols)]:
            st.metric(row["label"], row["value"])
    if snapshot.daily_report_text:
        with st.expander("Daily report", expanded=False):
            st.markdown(snapshot.daily_report_text)
    else:
        st.caption("No daily report available yet.")


def render_safe_ops() -> None:
    st.subheader("Safe operator controls")
    if st.button("Run offline evolution now", use_container_width=True):
        result = run_safe_command(build_offline_evolution_command())
        if result["returncode"] == 0:
            st.success("Offline evolution completed.")
        else:
            st.error("Offline evolution failed.")
        if result["stdout"]:
            st.code(f"STDOUT:\n{result['stdout']}", language="text")
        if result["stderr"]:
            st.code(f"STDERR:\n{result['stderr']}", language="text")


def render_runtime_fragment(
    log_path: Path,
    env_path: Path,
    harness_meta_path: Path,
) -> None:
    if st.button("Refresh runtime data", key="refresh_runtime", use_container_width=True):
        bump_refresh_nonce("runtime")
        st.rerun(scope="fragment")

    refresh_nonce = get_refresh_nonce("runtime")
    env_settings = load_env_settings(str(env_path), refresh_nonce=refresh_nonce)
    header_context = build_header_context(
        env_settings=env_settings,
        harness_meta=load_harness_meta(harness_meta_path, refresh_nonce=refresh_nonce),
    )
    state = build_state(log_path, env_settings)
    render_monitor_body(state, header_context)


def render_evolution_fragment(
    evolution_dir: Path,
    harness_meta_path: Path,
) -> None:
    if st.button("Refresh evolution data", key="refresh_evolution", use_container_width=True):
        bump_refresh_nonce("evolution")
        st.rerun(scope="fragment")

    refresh_nonce = get_refresh_nonce("evolution")
    snapshot = load_latest_evolution_snapshot(
        evolution_dir,
        harness_meta_path=harness_meta_path,
        refresh_nonce=refresh_nonce,
    )
    render_evolution_summary(snapshot)


def render_control_fragment(control_state_path: Path, harness_meta_path: Path) -> None:
    if st.button("Refresh control state", key="refresh_control", use_container_width=True):
        bump_refresh_nonce("control")
        st.rerun(scope="fragment")

    control_state = load_control_state(control_state_path)
    harness_meta = load_harness_meta(harness_meta_path, refresh_nonce=get_refresh_nonce("control"))
    render_control_panel(control_state_path, control_state, harness_meta=harness_meta)


def render_debug_fragment(
    log_path: Path,
    env_path: Path,
    control_state_path: Path,
    evolution_dir: Path,
    harness_meta_path: Path,
) -> None:
    if st.button("Refresh debug data", key="refresh_debug", use_container_width=True):
        bump_refresh_nonce("debug")
        st.rerun(scope="fragment")

    refresh_nonce = get_refresh_nonce("debug")
    env_settings = load_env_settings(str(env_path), refresh_nonce=refresh_nonce)
    state = build_state(log_path, env_settings)
    snapshot = load_latest_evolution_snapshot(
        evolution_dir,
        harness_meta_path=harness_meta_path,
        refresh_nonce=refresh_nonce,
    )
    st.subheader("Debug")
    st.caption("Support view for source paths and raw payloads. Keep this off the main monitor flow.")
    st.markdown(
        "\n".join(
            [
                f"- **Log source:** `{state.log_path}`",
                f"- **Env source:** `{env_path}`",
                f"- **Control state:** `{control_state_path}`",
                f"- **Evolution dir:** `{evolution_dir}`",
                f"- **Harness meta:** `{harness_meta_path}`",
            ]
        )
    )
    st.markdown("#### Raw latest payload")
    render_raw_view(state)
    if snapshot.harness_meta:
        st.markdown("#### Latest harness meta")
        st.json(snapshot.harness_meta)


def render_control_panel(
    control_state_path: Path,
    state: ControlState,
    *,
    harness_meta: dict[str, Any] | None = None,
) -> None:
    st.subheader("Runtime controls")
    active_harness_version = "local"
    if isinstance(harness_meta, dict):
        active_harness_version = str(harness_meta.get("harness_version") or "local")
    st.caption(f"Control state: {control_state_path}")
    st.info(f"Active harness version: `{active_harness_version}`")

    with st.expander("Live control", expanded=True):
        st.warning(
            "Live toggle only controls whether the local supervisor runs agent cycles. "
            "It does not submit manual trade actions from the UI."
        )

        live_enabled = st.toggle(
            "Enable live agent loop",
            value=state.live_enabled,
            help="When enabled, `python3 -m tradeharness.supervisor` will run live cycles.",
        )
        if live_enabled != state.live_enabled:
            save_control_state(
                control_state_path,
                ControlState(
                    live_enabled=live_enabled,
                    offline_evolution_enabled=state.offline_evolution_enabled,
                    offline_evolution_time=state.offline_evolution_time,
                    last_offline_evolution_run_date=state.last_offline_evolution_run_date,
                    strategy=state.strategy,
                    risk=state.risk,
                ),
            )
            st.success("Live control updated.")
            st.rerun()
            return

        with st.form("offline-evolution-schedule"):
            offline_evolution_enabled = st.checkbox(
                "Enable scheduled offline evolution",
                value=state.offline_evolution_enabled,
            )
            offline_evolution_time = st.time_input(
                "Offline evolution time",
                value=_parse_control_time(state.offline_evolution_time),
                step=timedelta(minutes=15),
            )
            submitted = st.form_submit_button("Save schedule", use_container_width=True)
            if submitted:
                save_control_state(
                    control_state_path,
                    ControlState(
                        live_enabled=live_enabled,
                        offline_evolution_enabled=offline_evolution_enabled,
                        offline_evolution_time=_format_control_time(offline_evolution_time),
                        last_offline_evolution_run_date=state.last_offline_evolution_run_date,
                        strategy=state.strategy,
                        risk=state.risk,
                    ),
                )
                st.success("Offline evolution schedule updated.")
                st.rerun()
                return

    with st.expander("Strategy", expanded=False):
        with st.form("strategy-controls"):
            st.markdown("### Strategy settings")
            strategy_options = ["random_flip", "manual_only"]
            strategy_index = (
                strategy_options.index(state.strategy.mode)
                if state.strategy.mode in strategy_options
                else 0
            )
            strategy_mode = st.selectbox(
                "Strategy mode",
                options=strategy_options,
                index=strategy_index,
                help="`random_flip` opens random long/short and closes on timer. `manual_only` keeps the loop alive without placing trades.",
            )
            entry_quantity_btc = st.number_input(
                "Entry size (BTC)",
                min_value=0.001,
                max_value=10.0,
                value=float(state.strategy.entry_quantity_btc),
                step=0.001,
                format="%.3f",
            )
            hold_seconds = st.number_input(
                "Hold seconds",
                min_value=1,
                max_value=86400,
                value=int(state.strategy.hold_seconds),
                step=1,
            )
            cooldown_seconds = st.number_input(
                "Cooldown seconds",
                min_value=0,
                max_value=86400,
                value=int(state.strategy.cooldown_seconds),
                step=1,
            )
            strategy_submitted = st.form_submit_button("Save strategy", use_container_width=True)
            if strategy_submitted:
                save_control_state(
                    control_state_path,
                    ControlState(
                        live_enabled=live_enabled,
                        offline_evolution_enabled=state.offline_evolution_enabled,
                        offline_evolution_time=state.offline_evolution_time,
                        last_offline_evolution_run_date=state.last_offline_evolution_run_date,
                        strategy=StrategyControlState(
                            mode=strategy_mode,
                            entry_quantity_btc=float(entry_quantity_btc),
                            hold_seconds=int(hold_seconds),
                            cooldown_seconds=int(cooldown_seconds),
                        ),
                        risk=state.risk,
                    ),
                )
                st.success("Strategy updated.")
                st.rerun()
                return

    with st.expander("Risk guard", expanded=False):
        with st.form("risk-controls"):
            st.markdown("### Risk guard")
            max_daily_loss_usdt = st.number_input(
                "Max daily loss (USDT)",
                min_value=0.0,
                max_value=1_000_000.0,
                value=float(state.risk.max_daily_loss_usdt),
                step=5.0,
                format="%.2f",
            )
            max_open_positions = st.number_input(
                "Max open positions",
                min_value=0,
                max_value=100,
                value=int(state.risk.max_open_positions),
                step=1,
            )
            loss_cooldown_seconds = st.number_input(
                "Loss cooldown seconds",
                min_value=0,
                max_value=86400,
                value=int(state.risk.loss_cooldown_seconds),
                step=60,
            )
            hard_stop_candle_range_pct = st.number_input(
                "Hard stop candle range %",
                min_value=0.0,
                max_value=100.0,
                value=float(state.risk.hard_stop_candle_range_pct),
                step=0.1,
                format="%.2f",
            )
            risk_submitted = st.form_submit_button("Save risk guard", use_container_width=True)
            if risk_submitted:
                save_control_state(
                    control_state_path,
                    ControlState(
                        live_enabled=live_enabled,
                        offline_evolution_enabled=state.offline_evolution_enabled,
                        offline_evolution_time=state.offline_evolution_time,
                        last_offline_evolution_run_date=state.last_offline_evolution_run_date,
                        strategy=state.strategy,
                        risk=RiskControlState(
                            max_daily_loss_usdt=float(max_daily_loss_usdt),
                            max_open_positions=int(max_open_positions),
                            loss_cooldown_seconds=int(loss_cooldown_seconds),
                            hard_stop_candle_range_pct=float(hard_stop_candle_range_pct),
                        ),
                    ),
                )
                st.success("Risk guard updated.")
                st.rerun()
                return

    with st.expander("Safe ops", expanded=False):
        render_safe_ops()


render_runtime_fragment = st.fragment(render_runtime_fragment, run_every=10)
render_evolution_fragment = st.fragment(render_evolution_fragment, run_every=30)
render_control_fragment = st.fragment(render_control_fragment, run_every=15)


def render_raw_view(state: DashboardState) -> None:
    st.subheader("Raw latest payload")
    if state.latest is None:
        st.code("{}", language="json")
        return
    st.json(state.latest.raw)


def main() -> None:
    st.set_page_config(page_title="TradeHarness Operator Console", layout="wide")
    st.sidebar.header("Settings")
    default_log = os.getenv("TRAJECTORY_LOG_PATH", str(DEFAULT_LOG_PATH))
    log_path_input = st.sidebar.text_input("Trajectory log path", value=default_log)
    st.sidebar.caption("Use the tabs below for monitor, controls, evolution, and debug.")

    dashboard_paths = resolve_dashboard_paths(Path(log_path_input))
    monitor_tab, controls_tab, evolution_tab, debug_tab = st.tabs(
        ["Monitor", "Controls", "Evolution", "Debug"]
    )

    with monitor_tab:
        render_runtime_fragment(
            dashboard_paths["log_path"],
            dashboard_paths["env_path"],
            dashboard_paths["harness_meta_path"],
        )
    with controls_tab:
        render_control_fragment(
            dashboard_paths["control_state_path"],
            dashboard_paths["harness_meta_path"],
        )
    with evolution_tab:
        render_evolution_fragment(
            dashboard_paths["evolution_dir"],
            dashboard_paths["harness_meta_path"],
        )
    with debug_tab:
        render_debug_fragment(
            dashboard_paths["log_path"],
            dashboard_paths["env_path"],
            dashboard_paths["control_state_path"],
            dashboard_paths["evolution_dir"],
            dashboard_paths["harness_meta_path"],
        )


if __name__ == "__main__":
    main()
