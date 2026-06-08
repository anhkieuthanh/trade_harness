from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    binance_api_key: str
    binance_api_secret: str
    lmstudio_base_url: str
    lmstudio_model: str
    symbol: str
    poll_interval_seconds: int
    candle_interval: str
    candle_limit: int
    trade_size_percent: float
    dry_run: bool
    evaluator_base_url: str
    evaluator_api_key: str
    evaluator_model: str
    trajectory_log_path: str
    evolution_output_dir: str
    evolution_runs_dir: str
    evolution_minimum_support: int
    active_contract_artifact_path: str
    active_skills_artifact_path: str
    active_action_rules_artifact_path: str
    active_trajectory_rules_artifact_path: str
    active_harness_meta_artifact_path: str
    harness_version: str
    task_id: str


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _load_dotenv_file(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def _load_harness_version(*, meta_path: str, fallback: str) -> str:
    if not os.path.exists(meta_path):
        return fallback
    try:
        with open(meta_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return fallback

    resolved = str(payload.get("harness_version", "")).strip()
    return resolved or fallback


def load_settings() -> Settings:
    _load_dotenv_file()
    symbol = os.getenv("SYMBOL", "BTCUSDT")
    candle_interval = os.getenv("CANDLE_INTERVAL", "1m")
    candle_limit = int(os.getenv("CANDLE_LIMIT", "5"))
    active_harness_meta_artifact_path = os.getenv(
        "ACTIVE_HARNESS_META_ARTIFACT_PATH",
        "tradeharness/evolution/artifacts/current/harness_meta.json",
    )
    return Settings(
        binance_api_key=os.environ["BINANCE_API_KEY"],
        binance_api_secret=os.environ["BINANCE_API_SECRET"],
        lmstudio_base_url=os.getenv("LMSTUDIO_BASE_URL", "http://192.168.10.17:1234/v1"),
        lmstudio_model=os.getenv("LMSTUDIO_MODEL", "google/gemma-4-e2b"),
        symbol=symbol,
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "30")),
        candle_interval=candle_interval,
        candle_limit=candle_limit,
        trade_size_percent=float(os.getenv("TRADE_SIZE_PERCENT", "10")),
        dry_run=_parse_bool(os.getenv("DRY_RUN", "true")),
        evaluator_base_url=os.getenv("EVALUATOR_BASE_URL", "https://example.invalid/v1"),
        evaluator_api_key=os.getenv("EVALUATOR_API_KEY", ""),
        evaluator_model=os.getenv("EVALUATOR_MODEL", "gpt-5.4"),
        trajectory_log_path=os.getenv(
            "TRAJECTORY_LOG_PATH",
            "var/trajectories/episodes.jsonl",
        ),
        evolution_output_dir=os.getenv("EVOLUTION_OUTPUT_DIR", "var/evolution"),
        evolution_runs_dir=os.getenv("EVOLUTION_RUNS_DIR", "var/evolution/runs"),
        evolution_minimum_support=int(os.getenv("EVOLUTION_MINIMUM_SUPPORT", "1")),
        active_contract_artifact_path=os.getenv(
            "ACTIVE_CONTRACT_ARTIFACT_PATH",
            "tradeharness/evolution/artifacts/current/contract.json",
        ),
        active_skills_artifact_path=os.getenv(
            "ACTIVE_SKILLS_ARTIFACT_PATH",
            "tradeharness/evolution/artifacts/current/skills.json",
        ),
        active_action_rules_artifact_path=os.getenv(
            "ACTIVE_ACTION_RULES_ARTIFACT_PATH",
            "tradeharness/evolution/artifacts/current/action_rules.json",
        ),
        active_trajectory_rules_artifact_path=os.getenv(
            "ACTIVE_TRAJECTORY_RULES_ARTIFACT_PATH",
            "tradeharness/evolution/artifacts/current/trajectory_rules.json",
        ),
        active_harness_meta_artifact_path=active_harness_meta_artifact_path,
        harness_version=_load_harness_version(
            meta_path=active_harness_meta_artifact_path,
            fallback=os.getenv("HARNESS_VERSION", "local"),
        ),
        task_id=os.getenv(
            "TASK_ID",
            f"trade:{symbol}:{candle_interval}:{candle_limit}:inspect_then_decide",
        ),
    )
