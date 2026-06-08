from __future__ import annotations

import json
from datetime import datetime, timezone
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
from tradeharness.runtime.trajectory_regulation.monitor import regulate_trajectory
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
        symbol=symbol,
        mode=mode,
        started_at=started_at,
        ended_at=ended_at,
        final_status=final_status,
        termination_reason=termination_reason,
        steps=steps,
        final_outcome=final_outcome,
    )


def run_agent_cycle(settings: Settings) -> None:
    episode_id = f"episode-{uuid4().hex}"
    started_at = datetime.now(timezone.utc).isoformat()
    episode_steps: list[dict[str, Any]] = []

    def finalize_episode(
        *,
        final_status: str,
        termination_reason: str,
        final_outcome: dict[str, Any],
    ) -> None:
        append_episode_record(
            settings.trajectory_log_path,
            build_episode_termination_record(
                episode_id=episode_id,
                symbol=settings.symbol,
                mode="dry_run" if settings.dry_run else "live",
                started_at=started_at,
                ended_at=datetime.now(timezone.utc).isoformat(),
                steps=episode_steps,
                final_status=final_status,
                termination_reason=termination_reason,
                final_outcome=final_outcome,
            ),
        )

    binance = BinanceFuturesTestnetClient(
        settings.binance_api_key,
        settings.binance_api_secret,
    )
    llm = LMStudioClient(settings.lmstudio_base_url, settings.lmstudio_model)
    toolset = BinanceToolset(
        binance,
        trade_size_percent=settings.trade_size_percent,
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

                tool_result = toolset.run_tool(tool_request.name, tool_request.arguments)
                print(f"tool={tool_request.name} result={json.dumps(tool_result)}")
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
