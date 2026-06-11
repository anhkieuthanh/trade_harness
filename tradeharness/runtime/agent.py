from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from tradeharness.config.settings import Settings
from tradeharness.evolution.schemas import build_episode_record, build_step_record
from tradeharness.evolution.storage.trajectories import append_episode_record
from tradeharness.integrations.binance.client import BinanceFuturesTestnetClient
from tradeharness.integrations.lmstudio.client import (
    LMStudioClient,
    extract_tool_requests,
    get_message_content,
)
from tradeharness.runtime.action_realization.gate import (
    EXECUTION_TOOL_NAMES,
    MAX_ACTION_REALIZATION_RETRIES,
    realize_action,
)
from tradeharness.runtime.contracts.environment import build_environment_contract
from tradeharness.runtime.skills.prompting import (
    build_skill_query,
    render_relevant_skills_block,
)
from tradeharness.runtime.skills.retrieval import retrieve_relevant_skills
from tradeharness.runtime.risk import (
    LiveRiskControl,
    evaluate_live_risk,
    load_live_risk_state,
    record_trade_close,
    save_live_risk_state,
)
from tradeharness.runtime.trajectory_regulation.monitor import regulate_trajectory
from tradeharness.runtime.strategies import RSIState, get_trade_strategy
from tradeharness.tools.binance import BinanceToolset

BASE_SYSTEM_PROMPT = """You are a BTCUSDT Binance Futures Testnet trading agent.
Your brain runs in LM Studio. Your only way to inspect or act on Binance is through the provided tools.

Rules:
- Use tools to inspect market state, balance, and position before trading.
- Prefer get_market_snapshot, get_balance, and get_position before open_long, open_short, or close_position.
- If native tool calling is unavailable, return strict JSON like {"tool":"get_market_snapshot","arguments":{"symbol":"BTCUSDT","interval":"1m","limit":5}}.
- When you are done and no more tool calls are needed, return strict JSON like {"final":"short operator summary"}.
- Never mention tools that do not exist.
"""


def _format_runtime_exception(exc: Exception) -> str:
    return f"{exc.__class__.__name__}: {exc}"


def build_system_prompt(*, symbol: str, relevant_skills_block: str) -> str:
    return "\n\n".join(
        [
            BASE_SYSTEM_PROMPT,
            build_environment_contract(symbol),
            relevant_skills_block,
        ]
    )


def build_action_block_feedback(block_result: dict[str, Any]) -> str:
    return (
        "Action blocked by Action Realization Layer. "
        f"Reason: {block_result['reason']} "
        "Please inspect the latest state and propose a corrected action or return a final no-trade summary."
    )


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


def build_risk_block_feedback(risk_reason: str) -> str:
    return (
        "Live Risk Guard blocked this action. "
        f"Reason: {risk_reason} "
        "Protect capital first, then re-evaluate the market."
    )


def build_runtime_step_record(
    *,
    step_index: int,
    observation: dict[str, Any],
    decision_summary: str,
    action: dict[str, Any],
    harness_intervention: dict[str, Any],
    environment_feedback: dict[str, Any],
) -> dict[str, Any]:
    return build_step_record(
        step_index=step_index,
        observation=observation,
        decision_summary=decision_summary,
        action=action,
        harness_intervention=harness_intervention,
        environment_feedback=environment_feedback,
    )


def build_episode_termination_record(
    *,
    episode_id: str,
    task_id: str,
    harness_version: str,
    symbol: str,
    mode: str,
    started_at: str,
    ended_at: str,
    steps: list[dict[str, Any]],
    final_status: str,
    termination_reason: str,
    final_outcome: dict[str, Any],
    ) -> dict[str, Any]:
    return build_episode_record(
        episode_id=episode_id,
        task_id=task_id,
        harness_version=harness_version,
        symbol=symbol,
        mode=mode,
        started_at=started_at,
        ended_at=ended_at,
        final_status=final_status,
        termination_reason=termination_reason,
        steps=steps,
        final_outcome=final_outcome,
    )


def _format_strategy_summary(action: str, quantity: float, hold_seconds: int, strategy_name: str) -> str:
    if action == "close_position":
        return (
            f"{strategy_name} strategy closed the position after {hold_seconds} seconds."
        )
    side = "LONG" if action == "open_long" else "SHORT"
    return (
        f"{strategy_name} strategy opened {side} with fixed size {quantity:.3f} BTC. "
        f"Hold for {hold_seconds} seconds before closing."
    )


_LLM_VETO_CONFIDENCE_THRESHOLD = 40  # Veto entry if LLM confidence < this value


def _build_rsi_reasoning_prompt(
    *,
    symbol: str,
    action: str,
    rsi_value: float,
    candles: list[dict[str, Any]],
    balance_usdt: float,
    position_state: dict[str, Any],
) -> str:
    side = "LONG" if action == "open_long" else "SHORT"
    recent = candles[-5:] if len(candles) >= 5 else candles
    candle_summary = "; ".join(
        f"[O:{c.get('open','?')} H:{c.get('high','?')} L:{c.get('low','?')} C:{c.get('close','?')}]"
        for c in recent
    )
    position_summary = (
        f"OPEN {position_state.get('side')} qty={position_state.get('quantity')}"
        if position_state.get("is_open")
        else "NO POSITION"
    )
    return (
        f"You are a crypto trading analyst reviewing a RSI-7 signal on {symbol} (5m candles).\n"
        f"RSI value: {rsi_value:.2f}\n"
        f"Signal: {side} ({action})\n"
        f"Reason: {'RSI oversold (<= 30)' if action == 'open_long' else 'RSI overbought (>= 70)'}\n"
        f"Last 5 candles (OHLC): {candle_summary}\n"
        f"Available balance: {balance_usdt:.2f} USDT\n"
        f"Current position: {position_summary}\n\n"
        "Based on the above, evaluate whether this RSI signal is reliable right now.\n"
        "Consider: candle patterns, balance sufficiency, overall momentum direction.\n"
        "Return ONLY valid JSON, no markdown, no explanation outside JSON:\n"
        '{"confidence": <0-100>, "reasoning": "<1-2 sentence explanation>", "market_context": "<brief market description>"}'
    )


def _get_llm_reasoning(
    *,
    llm: LMStudioClient,
    action: str,
    rsi_value: float,
    candles: list[dict[str, Any]],
    balance_usdt: float,
    position_state: dict[str, Any],
    symbol: str,
) -> dict[str, Any]:
    """Ask LLM for a confidence score on the RSI entry signal.

    Returns a dict with keys: confidence, reasoning, market_context, veto, error.
    Never raises — always returns a safe fallback on failure.
    """
    try:
        prompt = _build_rsi_reasoning_prompt(
            symbol=symbol,
            action=action,
            rsi_value=rsi_value,
            candles=candles,
            balance_usdt=balance_usdt,
            position_state=position_state,
        )
        raw = llm.chat(prompt)
        payload = json.loads(raw)
        confidence = int(payload.get("confidence", 50))
        veto = confidence < _LLM_VETO_CONFIDENCE_THRESHOLD
        return {
            "confidence": confidence,
            "reasoning": str(payload.get("reasoning", "")),
            "market_context": str(payload.get("market_context", "")),
            "veto": veto,
            "error": None,
            "skipped": False,
        }
    except Exception as exc:
        # Graceful fallback: LLM unavailable → do NOT veto (infra failure != bad signal)
        print(f"llm_reasoning=ERROR fallback_allow reason={exc.__class__.__name__}: {exc}")
        return {
            "confidence": None,
            "reasoning": None,
            "market_context": None,
            "veto": False,
            "error": f"{exc.__class__.__name__}: {exc}",
            "skipped": True,
        }


def _run_programmatic_strategy_cycle(
    *,
    settings: Settings,
    toolset: BinanceToolset,
    initial_market_snapshot: dict[str, Any],
    initial_position_state: dict[str, Any],
    episode_id: str,
    started_at: str,
    finalize_episode: Any,
) -> None:
    strategy_state_path = Path(settings.trade_strategy_state_path)
    risk_state_path = Path(settings.trade_risk_state_path)
    trade_strategy = get_trade_strategy(settings.trade_strategy_mode)
    strategy_state = trade_strategy.load_state(strategy_state_path)
    risk_state = load_live_risk_state(risk_state_path)
    current_position_state = dict(initial_position_state)
    now = datetime.now(timezone.utc)
    llm = LMStudioClient(settings.lmstudio_base_url, settings.lmstudio_model)

    if current_position_state.get("is_open") and strategy_state.opened_at is None:
        strategy_state = RSIState(
            opened_at=now.isoformat(),
            side=str(current_position_state.get("side", "")) or None,
            quantity=abs(float(current_position_state.get("quantity", 0.0))) or None,
        )
        trade_strategy.save_state(strategy_state_path, strategy_state)

    plan = trade_strategy.build_plan(
        position_state=current_position_state,
        strategy_state=strategy_state,
        now=now,
        hold_seconds=settings.trade_hold_seconds,
        cooldown_seconds=settings.trade_cooldown_seconds,
        market_snapshot=initial_market_snapshot,
    )

    episode_steps: list[dict[str, Any]] = []
    inspected_state = {
        "market_snapshot": True,
        "position": True,
        "balance": True,
    }

    balance_state = toolset.run_tool("get_balance", {"asset": "USDT"})
    current_position_state = toolset.run_tool("get_position", {"symbol": settings.symbol})

    current_balance = float(balance_state["available_balance"])
    risk_decision, risk_state = evaluate_live_risk(
        control=LiveRiskControl(
            max_daily_loss_usdt=settings.trade_risk_max_daily_loss_usdt,
            max_open_positions=settings.trade_risk_max_open_positions,
            loss_cooldown_seconds=settings.trade_risk_loss_cooldown_seconds,
            hard_stop_candle_range_pct=settings.trade_risk_hard_stop_candle_range_pct,
        ),
        runtime_state=risk_state,
        market_snapshot=initial_market_snapshot,
        position_state=current_position_state,
        current_balance_usdt=current_balance,
        planned_action=plan.action,
        now=now,
    )
    save_live_risk_state(risk_state_path, risk_state)

    if risk_decision.decision == "FORCE_CLOSE" and plan.action != "close_position":
        plan = type(plan)(action="close_position", reason=risk_decision.reason, side=None)
    elif risk_decision.decision == "BLOCK" and plan.action in {"open_long", "open_short"}:
        hold_label = (
            "manual_only_hold"
            if settings.trade_strategy_mode == "manual_only"
            else "risk_guard_hold"
        )
        summary = json.dumps(
            {
                "final": hold_label,
                "reason": risk_decision.reason,
                "risk": {
                    "daily_loss_usdt": risk_decision.daily_loss_usdt,
                    "current_position_count": risk_decision.current_position_count,
                    "candle_range_pct": risk_decision.candle_range_pct,
                },
            }
        )
        episode_steps.append(
            build_runtime_step_record(
                step_index=1,
                observation={
                    "market_snapshot": initial_market_snapshot,
                    "position_state": current_position_state,
                    "balance_state": balance_state,
                    "strategy_state": {
                        "opened_at": strategy_state.opened_at,
                        "side": strategy_state.side,
                        "quantity": strategy_state.quantity,
                    },
                    "risk_state": {
                        "session_day": risk_state.session_day,
                        "day_start_balance_usdt": risk_state.day_start_balance_usdt,
                        "last_loss_at": risk_state.last_loss_at,
                        "hard_stop_reason": risk_state.hard_stop_reason,
                    },
                },
                decision_summary=risk_decision.reason,
                action={"final_response": summary},
                harness_intervention={
                    "decision": "BLOCK",
                    "layer": "risk",
                    "risk": {
                        "daily_loss_usdt": risk_decision.daily_loss_usdt,
                        "current_position_count": risk_decision.current_position_count,
                        "candle_range_pct": risk_decision.candle_range_pct,
                    },
                },
                environment_feedback={
                    "blocked": True,
                    "feedback": build_risk_block_feedback(risk_decision.reason),
                },
            )
        )
        finalize_episode(
            final_status="SUCCESS",
            termination_reason=hold_label,
            final_outcome={"final": summary},
            steps=episode_steps,
        )
        print(f"agent={summary}")
        return
    elif risk_decision.decision == "FORCE_CLOSE":
        plan = type(plan)(action="close_position", reason=risk_decision.reason, side=None)

    if plan.action == "hold":
        if risk_decision.decision == "BLOCK":
            hold_label = "risk_guard_hold"
            hold_reason = risk_decision.reason
            hold_intervention = {
                "decision": "BLOCK",
                "layer": "risk",
                "risk": {
                    "daily_loss_usdt": risk_decision.daily_loss_usdt,
                    "current_position_count": risk_decision.current_position_count,
                    "candle_range_pct": risk_decision.candle_range_pct,
                },
            }
            hold_feedback = build_risk_block_feedback(risk_decision.reason)
        else:
            hold_label = (
                "manual_only_hold"
                if settings.trade_strategy_mode == "manual_only"
                else f"{trade_strategy.name}_hold"
            )
            hold_reason = plan.reason
            hold_intervention = {"decision": "ALLOW", "layer": "strategy"}
            hold_feedback = {"emitted": True}
        summary = json.dumps(
            {
                "final": hold_label,
                "reason": hold_reason,
                "hold_seconds": settings.trade_hold_seconds,
            }
        )
        episode_steps.append(
            build_runtime_step_record(
                step_index=1,
                observation={
                    "market_snapshot": initial_market_snapshot,
                    "position_state": current_position_state,
                    "strategy_state": {
                        "opened_at": strategy_state.opened_at,
                        "side": strategy_state.side,
                        "quantity": strategy_state.quantity,
                    },
                    "risk_state": {
                        "session_day": risk_state.session_day,
                        "day_start_balance_usdt": risk_state.day_start_balance_usdt,
                        "last_loss_at": risk_state.last_loss_at,
                        "hard_stop_reason": risk_state.hard_stop_reason,
                    },
                },
                decision_summary=hold_reason,
                action={"final_response": summary},
                harness_intervention=hold_intervention,
                environment_feedback=hold_feedback,
            )
        )
        finalize_episode(
            final_status="SUCCESS",
            termination_reason=hold_label,
            final_outcome={"final": summary},
            steps=episode_steps,
        )
        print(f"agent={summary}")
        return

    # ── LLM Veto Check (Option B) ──────────────────────────────────────────
    # Only run when RSI proposes opening a new position — not for HOLD/CLOSE.
    llm_reasoning: dict[str, Any] = {"skipped": True}
    if plan.action in {"open_long", "open_short"}:
        rsi_value = trade_strategy.calculate_rsi(
            initial_market_snapshot.get("candles", []), period=7
        )
        llm_reasoning = _get_llm_reasoning(
            llm=llm,
            action=plan.action,
            rsi_value=rsi_value,
            candles=initial_market_snapshot.get("candles", []),
            balance_usdt=current_balance,
            position_state=current_position_state,
            symbol=settings.symbol,
        )
        print(
            f"llm_reasoning=DONE confidence={llm_reasoning.get('confidence')} "
            f"veto={llm_reasoning.get('veto')} "
            f"reason={llm_reasoning.get('reasoning')!r}"
        )
        if llm_reasoning.get("veto"):
            veto_reason = (
                f"LLM veto: confidence {llm_reasoning['confidence']}% < "
                f"{_LLM_VETO_CONFIDENCE_THRESHOLD}% threshold — "
                f"{llm_reasoning.get('reasoning', '')}"
            )
            summary = json.dumps(
                {
                    "final": "llm_veto_hold",
                    "reason": veto_reason,
                    "llm_confidence": llm_reasoning["confidence"],
                    "llm_reasoning": llm_reasoning.get("reasoning"),
                    "market_context": llm_reasoning.get("market_context"),
                }
            )
            episode_steps.append(
                build_runtime_step_record(
                    step_index=1,
                    observation={
                        "market_snapshot": initial_market_snapshot,
                        "position_state": current_position_state,
                        "balance_state": balance_state,
                        "strategy_state": {
                            "opened_at": strategy_state.opened_at,
                            "side": strategy_state.side,
                            "quantity": strategy_state.quantity,
                        },
                        "risk_state": {
                            "session_day": risk_state.session_day,
                            "day_start_balance_usdt": risk_state.day_start_balance_usdt,
                            "last_loss_at": risk_state.last_loss_at,
                            "hard_stop_reason": risk_state.hard_stop_reason,
                        },
                        "llm_reasoning": llm_reasoning,
                    },
                    decision_summary=veto_reason,
                    action={"final_response": summary},
                    harness_intervention={
                        "decision": "BLOCK",
                        "layer": "llm_reasoning",
                        "confidence": llm_reasoning["confidence"],
                        "threshold": _LLM_VETO_CONFIDENCE_THRESHOLD,
                    },
                    environment_feedback={"blocked": True, "feedback": veto_reason},
                )
            )
            finalize_episode(
                final_status="SUCCESS",
                termination_reason="llm_veto_hold",
                final_outcome={"final": summary},
                steps=episode_steps,
            )
            print(f"agent={summary}")
            return
    # ── End LLM Veto ──────────────────────────────────────────────────────

    gate_result = realize_action(
        tool_name=plan.action,
        arguments={"symbol": settings.symbol},
        position_state=current_position_state,
        inspected_state=inspected_state,
    )
    if gate_result["decision"] == "BLOCK":
        summary = json.dumps(
            {
                "final": f"{trade_strategy.name}_blocked",
                "reason": gate_result["reason"],
            }
        )
        episode_steps.append(
            build_runtime_step_record(
                step_index=1,
                observation={
                    "market_snapshot": initial_market_snapshot,
                    "position_state": current_position_state,
                    "balance_state": balance_state,
                    "strategy_state": {
                        "opened_at": strategy_state.opened_at,
                        "side": strategy_state.side,
                        "quantity": strategy_state.quantity,
                    },
                    "risk_state": {
                        "session_day": risk_state.session_day,
                        "day_start_balance_usdt": risk_state.day_start_balance_usdt,
                        "last_loss_at": risk_state.last_loss_at,
                        "hard_stop_reason": risk_state.hard_stop_reason,
                    },
                },
                decision_summary=plan.reason,
                action={
                    "tool": plan.action,
                    "arguments": {"symbol": settings.symbol},
                },
                harness_intervention=gate_result,
                environment_feedback={
                    "blocked": True,
                    "feedback": build_action_block_feedback(gate_result),
                },
            )
        )
        finalize_episode(
            final_status="FAILED",
            termination_reason=f"{trade_strategy.name}_blocked_by_gate",
            final_outcome={"final": summary},
            steps=episode_steps,
        )
        print(f"agent={summary}")
        return

    try:
        tool_result = toolset.run_tool(plan.action, {"symbol": settings.symbol})
    except Exception as exc:
        error_message = _format_runtime_exception(exc)
        summary = json.dumps(
            {
                "final": "tool_execution_error",
                "reason": error_message,
                "tool": plan.action,
            }
        )
        episode_steps.append(
            build_runtime_step_record(
                step_index=1,
                observation={
                    "market_snapshot": initial_market_snapshot,
                    "position_state": current_position_state,
                    "balance_state": balance_state,
                    "strategy_state": {
                        "opened_at": strategy_state.opened_at,
                        "side": strategy_state.side,
                        "quantity": strategy_state.quantity,
                    },
                    "risk_state": {
                        "session_day": risk_state.session_day,
                        "day_start_balance_usdt": risk_state.day_start_balance_usdt,
                        "last_loss_at": risk_state.last_loss_at,
                        "hard_stop_reason": risk_state.hard_stop_reason,
                    },
                },
                decision_summary=plan.reason,
                action={
                    "tool": plan.action,
                    "arguments": {"symbol": settings.symbol},
                },
                harness_intervention={"decision": "ERROR", "layer": "execution"},
                environment_feedback={"error": error_message},
            )
        )
        finalize_episode(
            final_status="FAILED",
            termination_reason="tool_execution_error",
            final_outcome={"final": summary},
            steps=episode_steps,
        )
        print(f"agent={summary}")
        return
    if plan.action in {"open_long", "open_short"}:
        trade_strategy.save_state(
            strategy_state_path,
            RSIState(
                opened_at=now.isoformat(),
                side="LONG" if plan.action == "open_long" else "SHORT",
                quantity=settings.trade_entry_quantity_btc,
                last_closed_at=strategy_state.last_closed_at,
                entry_rsi=trade_strategy.calculate_rsi(initial_market_snapshot.get("candles", [])),
            ),
        )
    elif plan.action == "close_position":
        risk_state = record_trade_close(
            risk_state,
            position_state=current_position_state,
            exit_price=float(initial_market_snapshot["price"]),
            now=now,
        )
        save_live_risk_state(risk_state_path, risk_state)
        trade_strategy.save_state(
            strategy_state_path,
            RSIState(last_closed_at=now.isoformat()),
        )

    summary = json.dumps(
        {
            "final": _format_strategy_summary(
                plan.action,
                settings.trade_entry_quantity_btc,
                settings.trade_hold_seconds,
                trade_strategy.name,
            ),
            "tool_result": tool_result,
        }
    )
    episode_steps.append(
        build_runtime_step_record(
            step_index=1,
            observation={
                "market_snapshot": initial_market_snapshot,
                "position_state": current_position_state,
                "balance_state": balance_state,
                "strategy_state": {
                    "opened_at": strategy_state.opened_at,
                    "side": strategy_state.side,
                    "quantity": strategy_state.quantity,
                },
                "risk_state": {
                    "session_day": risk_state.session_day,
                    "day_start_balance_usdt": risk_state.day_start_balance_usdt,
                    "last_loss_at": risk_state.last_loss_at,
                    "hard_stop_reason": risk_state.hard_stop_reason,
                },
                "llm_reasoning": llm_reasoning,
            },
            decision_summary=plan.reason,
            action={
                "tool": plan.action,
                "arguments": {"symbol": settings.symbol},
            },
            harness_intervention={"decision": "EXECUTE", "layer": "strategy"},
            environment_feedback=tool_result,
        )
    )
    episode_steps.append(
        build_runtime_step_record(
            step_index=2,
            observation={"strategy_state": "post_action"},
            decision_summary=summary,
            action={"final_response": summary},
            harness_intervention={"decision": "ALLOW", "layer": "strategy"},
            environment_feedback={"emitted": True},
        )
    )
    finalize_episode(
        final_status="SUCCESS",
        termination_reason=f"{trade_strategy.name}_cycle_completed",
        final_outcome={"final": summary},
        steps=episode_steps,
    )
    print(f"agent={summary}")


def run_agent_cycle(settings: Settings) -> None:
    episode_id = f"episode-{uuid4().hex}"
    started_at = datetime.now(timezone.utc).isoformat()
    episode_steps: list[dict[str, Any]] = []

    def finalize_episode(
        *,
        final_status: str,
        termination_reason: str,
        final_outcome: dict[str, Any],
        steps: list[dict[str, Any]] | None = None,
    ) -> None:
        append_episode_record(
            settings.trajectory_log_path,
            build_episode_termination_record(
                episode_id=episode_id,
                task_id=settings.task_id,
                harness_version=settings.harness_version,
                symbol=settings.symbol,
                mode="dry_run" if settings.dry_run else "live",
                started_at=started_at,
                ended_at=datetime.now(timezone.utc).isoformat(),
                steps=steps if steps is not None else episode_steps,
                final_status=final_status,
                termination_reason=termination_reason,
                final_outcome=final_outcome,
            ),
        )

    try:
        binance = BinanceFuturesTestnetClient(
            settings.binance_api_key,
            settings.binance_api_secret,
        )
        llm = LMStudioClient(settings.lmstudio_base_url, settings.lmstudio_model)
        toolset = BinanceToolset(
            binance,
            trade_size_percent=settings.trade_size_percent,
            fixed_entry_quantity=settings.trade_entry_quantity_btc,
            dry_run=settings.dry_run,
        )
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

        if settings.trade_strategy_mode in {"rsi_strategy", "manual_only"}:
            _run_programmatic_strategy_cycle(
                settings=settings,
                toolset=toolset,
                initial_market_snapshot=initial_market_snapshot,
                initial_position_state=initial_position_state,
                episode_id=episode_id,
                started_at=started_at,
                finalize_episode=finalize_episode,
            )
            return

        skill_query = build_skill_query(
            user_task="Inspect state with tools first, then decide whether to trade.",
            symbol=settings.symbol,
            interval=settings.candle_interval,
            market_snapshot=initial_market_snapshot,
            position_state=initial_position_state,
            tool_intent="entry_execution",
        )
        relevant_skills = retrieve_relevant_skills(skill_query, top_k=2)
        relevant_skills_block = render_relevant_skills_block(relevant_skills)
        inspected_state = {
            "market_snapshot": True,
            "position": True,
            "balance": False,
        }
        blocked_attempts = 0
        trajectory_history: list[dict[str, Any]] = []

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

        for _ in range(6):
            response = llm.complete(messages, tools=toolset.definitions())
            assistant_message = response["choices"][0]["message"]
            tool_requests = extract_tool_requests(response)

            if tool_requests:
                messages.append(assistant_message)
                blocked_in_this_turn = False
                trajectory_warning_in_this_turn = False
                for tool_request in tool_requests:
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
                        blocked_in_this_turn = True
                        trajectory_history.append(
                            {
                                "event": "block",
                                "tool_name": tool_request.name,
                                "block_reason": gate_result["reason"],
                            }
                        )
                        messages.append(
                            {
                                "role": "user",
                                "content": build_action_block_feedback(gate_result),
                            }
                        )
                        episode_steps.append(
                            build_runtime_step_record(
                                step_index=len(episode_steps) + 1,
                                observation={
                                    "position_state": current_position_state,
                                    "inspected_state": dict(inspected_state),
                                },
                                decision_summary=get_message_content(response).strip()
                                or f"Requested tool {tool_request.name}.",
                                action={
                                    "tool": tool_request.name,
                                    "arguments": tool_request.arguments,
                                },
                                harness_intervention=gate_result,
                                environment_feedback={
                                    "blocked": True,
                                    "feedback": build_action_block_feedback(gate_result),
                                },
                            )
                        )
                        print(f"action_realization=BLOCK result={json.dumps(gate_result)}")
                        regulation_result = regulate_trajectory(
                            history=trajectory_history,
                            steps_remaining=6 - _ - 1,
                            final_answer_present=False,
                        )
                        if regulation_result["decision"] == "WARN":
                            trajectory_warning_in_this_turn = True
                            messages.append(
                                {
                                    "role": "user",
                                    "content": build_trajectory_warning_feedback(regulation_result),
                                }
                            )
                            print(
                                "trajectory_regulation=WARN "
                                f"result={json.dumps(regulation_result)}"
                            )
                        elif regulation_result["decision"] == "STOP":
                            print(
                                "trajectory_regulation=STOP "
                                f"result={json.dumps(regulation_result)}"
                            )
                            finalize_episode(
                                final_status="FAILED",
                                termination_reason="trajectory_regulation_stop",
                                final_outcome={
                                    "final": "trajectory_regulation_stop",
                                    "reason": regulation_result["reason"],
                                },
                            )
                            print(f"agent={build_trajectory_stop_summary(regulation_result)}")
                            return
                        if blocked_attempts > MAX_ACTION_REALIZATION_RETRIES:
                            finalize_episode(
                                final_status="FAILED",
                                termination_reason="blocked_by_action_realization_limit",
                                final_outcome={"final": "blocked_by_action_realization_limit"},
                            )
                            print('agent={"final":"blocked_by_action_realization_limit"}')
                            return
                        break

                    if tool_request.name in EXECUTION_TOOL_NAMES:
                        risk_state_path = Path(settings.trade_risk_state_path)
                        risk_state = load_live_risk_state(risk_state_path)

                        balance_state = toolset.run_tool("get_balance", {"asset": "USDT"})
                        current_balance = float(balance_state["available_balance"])

                        risk_decision, risk_state = evaluate_live_risk(
                            control=LiveRiskControl(
                                max_daily_loss_usdt=settings.trade_risk_max_daily_loss_usdt,
                                max_open_positions=settings.trade_risk_max_open_positions,
                                loss_cooldown_seconds=settings.trade_risk_loss_cooldown_seconds,
                                hard_stop_candle_range_pct=settings.trade_risk_hard_stop_candle_range_pct,
                            ),
                            runtime_state=risk_state,
                            market_snapshot=initial_market_snapshot,
                            position_state=current_position_state,
                            current_balance_usdt=current_balance,
                            planned_action=tool_request.name,
                            now=datetime.now(timezone.utc),
                        )
                        save_live_risk_state(risk_state_path, risk_state)

                        if risk_decision.decision in {"BLOCK", "FORCE_CLOSE"}:
                            if risk_decision.decision == "FORCE_CLOSE" and current_position_state.get("is_open"):
                                print(f"risk_guard=FORCE_CLOSE reason={risk_decision.reason}")
                                try:
                                    close_res = toolset.run_tool("close_position", {"symbol": settings.symbol})
                                    risk_state = record_trade_close(
                                        risk_state,
                                        position_state=current_position_state,
                                        exit_price=float(initial_market_snapshot["price"]),
                                        now=datetime.now(timezone.utc),
                                    )
                                    save_live_risk_state(risk_state_path, risk_state)
                                except Exception as exc:
                                    print(f"Failed to force close position: {exc}")

                            blocked_attempts += 1
                            blocked_in_this_turn = True
                            trajectory_history.append(
                                {
                                    "event": "block",
                                    "tool_name": tool_request.name,
                                    "block_reason": risk_decision.reason,
                                }
                            )
                            messages.append(
                                {
                                    "role": "user",
                                    "content": build_risk_block_feedback(risk_decision.reason),
                                }
                            )
                            episode_steps.append(
                                build_runtime_step_record(
                                    step_index=len(episode_steps) + 1,
                                    observation={
                                        "position_state": current_position_state,
                                        "inspected_state": dict(inspected_state),
                                        "balance_state": balance_state,
                                        "risk_state": {
                                            "session_day": risk_state.session_day,
                                            "day_start_balance_usdt": risk_state.day_start_balance_usdt,
                                            "last_loss_at": risk_state.last_loss_at,
                                            "hard_stop_reason": risk_state.hard_stop_reason,
                                        },
                                    },
                                    decision_summary=get_message_content(response).strip()
                                    or f"Requested tool {tool_request.name}.",
                                    action={
                                        "tool": tool_request.name,
                                        "arguments": tool_request.arguments,
                                    },
                                    harness_intervention={
                                        "decision": "BLOCK",
                                        "layer": "risk",
                                        "risk": {
                                            "daily_loss_usdt": risk_decision.daily_loss_usdt,
                                            "current_position_count": risk_decision.current_position_count,
                                            "candle_range_pct": risk_decision.candle_range_pct,
                                        },
                                    },
                                    environment_feedback={
                                        "blocked": True,
                                        "feedback": build_risk_block_feedback(risk_decision.reason),
                                    },
                                )
                            )
                            print(f"risk_guard=BLOCK reason={risk_decision.reason}")

                            if blocked_attempts > MAX_ACTION_REALIZATION_RETRIES:
                                finalize_episode(
                                    final_status="FAILED",
                                    termination_reason="blocked_by_live_risk_limit",
                                    final_outcome={"final": "blocked_by_live_risk_limit"},
                                )
                                print('agent={"final":"blocked_by_live_risk_limit"}')
                                return

                            regulation_result = regulate_trajectory(
                                history=trajectory_history,
                                steps_remaining=6 - _ - 1,
                                final_answer_present=False,
                            )
                            if regulation_result["decision"] == "WARN":
                                trajectory_warning_in_this_turn = True
                                messages.append(
                                    {
                                        "role": "user",
                                        "content": build_trajectory_warning_feedback(regulation_result),
                                    }
                                )
                            elif regulation_result["decision"] == "STOP":
                                finalize_episode(
                                    final_status="FAILED",
                                    termination_reason="trajectory_regulation_stop",
                                    final_outcome={
                                        "final": "trajectory_regulation_stop",
                                        "reason": regulation_result["reason"],
                                    },
                                )
                                return
                            break

                    tool_result = toolset.run_tool(tool_request.name, tool_request.arguments)
                    print(f"tool={tool_request.name} result={json.dumps(tool_result)}")

                    if tool_request.name == "close_position":
                        risk_state_path = Path(settings.trade_risk_state_path)
                        risk_state = load_live_risk_state(risk_state_path)
                        risk_state = record_trade_close(
                            risk_state,
                            position_state=current_position_state,
                            exit_price=float(initial_market_snapshot["price"]),
                            now=datetime.now(timezone.utc),
                        )
                        save_live_risk_state(risk_state_path, risk_state)

                    trajectory_history.append(
                        {
                            "event": "tool",
                            "tool_name": tool_request.name,
                            "blocked": False,
                        }
                    )
                    episode_steps.append(
                        build_runtime_step_record(
                            step_index=len(episode_steps) + 1,
                            observation={
                                "position_state": current_position_state,
                                "inspected_state": dict(inspected_state),
                            },
                            decision_summary=get_message_content(response).strip()
                            or f"Requested tool {tool_request.name}.",
                            action={
                                "tool": tool_request.name,
                                "arguments": tool_request.arguments,
                            },
                            harness_intervention={"decision": "EXECUTE", "layer": "none"},
                            environment_feedback=tool_result,
                        )
                    )
                    regulation_result = regulate_trajectory(
                        history=trajectory_history,
                        steps_remaining=6 - _ - 1,
                        final_answer_present=False,
                    )
                    if regulation_result["decision"] == "WARN":
                        trajectory_warning_in_this_turn = True
                        messages.append(
                            {
                                "role": "user",
                                "content": build_trajectory_warning_feedback(regulation_result),
                            }
                        )
                        print(
                            "trajectory_regulation=WARN "
                            f"result={json.dumps(regulation_result)}"
                        )
                        break
                    if regulation_result["decision"] == "STOP":
                        print(
                            "trajectory_regulation=STOP "
                            f"result={json.dumps(regulation_result)}"
                        )
                        finalize_episode(
                            final_status="FAILED",
                            termination_reason="trajectory_regulation_stop",
                            final_outcome={
                                "final": "trajectory_regulation_stop",
                                "reason": regulation_result["reason"],
                            },
                        )
                        print(f"agent={build_trajectory_stop_summary(regulation_result)}")
                        return
                    if tool_request.call_id:
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_request.call_id,
                                "name": tool_request.name,
                                "content": json.dumps(tool_result),
                            }
                        )
                    else:
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    f"Tool {tool_request.name} returned: {json.dumps(tool_result)}. "
                                    "If another tool is needed, request it. Otherwise return "
                                    '{"final":"..."}'
                                ),
                            }
                        )
                if blocked_in_this_turn:
                    continue
                if trajectory_warning_in_this_turn:
                    continue
                continue

            content = get_message_content(response).strip()
            regulation_result = regulate_trajectory(
                history=trajectory_history,
                steps_remaining=6 - _ - 1,
                final_answer_present=bool(content),
            )
            if regulation_result["decision"] == "STOP":
                print(
                    "trajectory_regulation=STOP "
                    f"result={json.dumps(regulation_result)}"
                )
                episode_steps.append(
                    build_runtime_step_record(
                        step_index=len(episode_steps) + 1,
                        observation={"trajectory_history_size": len(trajectory_history)},
                        decision_summary=content or "No final answer generated.",
                        action={"final_response": content},
                        harness_intervention=regulation_result,
                        environment_feedback={
                            "final": "trajectory_regulation_stop",
                            "reason": regulation_result["reason"],
                        },
                    )
                )
                finalize_episode(
                    final_status="FAILED",
                    termination_reason="trajectory_regulation_stop",
                    final_outcome={
                        "final": "trajectory_regulation_stop",
                        "reason": regulation_result["reason"],
                    },
                )
                print(f"agent={build_trajectory_stop_summary(regulation_result)}")
                return
            if content:
                episode_steps.append(
                    build_runtime_step_record(
                        step_index=len(episode_steps) + 1,
                        observation={"trajectory_history_size": len(trajectory_history)},
                        decision_summary=content,
                        action={"final_response": content},
                        harness_intervention={"decision": "ALLOW", "layer": "none"},
                        environment_feedback={"emitted": True},
                    )
                )
                finalize_episode(
                    final_status="SUCCESS",
                    termination_reason="final_response_returned",
                    final_outcome={"final": content},
                )
                print(f"agent={content}")
                return

        finalize_episode(
            final_status="FAILED",
            termination_reason="max_tool_steps_reached",
            final_outcome={"final": "max tool steps reached"},
        )
        print('agent={"final":"max tool steps reached"}')
    except Exception as exc:
        error_message = _format_runtime_exception(exc)
        finalize_episode(
            final_status="FAILED",
            termination_reason="unexpected_runtime_error",
            final_outcome={"final": "unexpected_runtime_error", "reason": error_message},
        )
        print(f'agent={{"final":"unexpected_runtime_error","reason":{json.dumps(error_message)}}}')
