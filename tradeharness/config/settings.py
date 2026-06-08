from __future__ import annotations

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


def load_settings() -> Settings:
    _load_dotenv_file()
    return Settings(
        binance_api_key=os.environ["BINANCE_API_KEY"],
        binance_api_secret=os.environ["BINANCE_API_SECRET"],
        lmstudio_base_url=os.getenv("LMSTUDIO_BASE_URL", "http://192.168.10.17:1234/v1"),
        lmstudio_model=os.getenv("LMSTUDIO_MODEL", "google/gemma-4-e2b"),
        symbol=os.getenv("SYMBOL", "BTCUSDT"),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "30")),
        candle_interval=os.getenv("CANDLE_INTERVAL", "1m"),
        candle_limit=int(os.getenv("CANDLE_LIMIT", "5")),
        trade_size_percent=float(os.getenv("TRADE_SIZE_PERCENT", "10")),
        dry_run=_parse_bool(os.getenv("DRY_RUN", "true")),
    )
