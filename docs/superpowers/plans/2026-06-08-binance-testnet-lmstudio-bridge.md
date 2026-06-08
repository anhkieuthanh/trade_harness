# Binance Testnet LM Studio Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal local Python worker that polls BTCUSDT market data from Binance Futures Testnet, asks LM Studio for a `BUY | SELL | HOLD | CLOSE` decision, and optionally sends the corresponding demo futures order.

**Architecture:** A single Python entrypoint coordinates four focused modules: config loading, Binance client, LM Studio client, and trading orchestration. The runtime stays intentionally narrow: one symbol, polling loop, percent-balance sizing, market orders only, and optional dry-run execution.

**Tech Stack:** Python 3, `requests`, `python-dotenv`, Binance Futures REST API, LM Studio OpenAI-compatible `/v1/chat/completions`

---

## File Structure

- Create: `TradeHarness/requirements.txt`
- Create: `TradeHarness/.env.example`
- Create: `TradeHarness/tradeharness/__init__.py`
- Create: `TradeHarness/tradeharness/config.py`
- Create: `TradeHarness/tradeharness/models.py`
- Create: `TradeHarness/tradeharness/binance_client.py`
- Create: `TradeHarness/tradeharness/llm_client.py`
- Create: `TradeHarness/tradeharness/decision_engine.py`
- Create: `TradeHarness/tradeharness/trader.py`
- Create: `TradeHarness/tradeharness/main.py`
- Modify: `TradeHarness/README.MD`

## Implementation Notes

- Use Binance Futures Testnet base URL, not spot or production endpoints.
- Use LM Studio's OpenAI-compatible API at `http://192.168.10.17:1234/v1` by default.
- Keep data contracts explicit with small dataclasses.
- Because the user explicitly narrowed scope, this plan uses smoke verification commands instead of formal test-first tasks for this phase.

### Task 1: Scaffold project skeleton and local setup files

**Files:**
- Create: `TradeHarness/requirements.txt`
- Create: `TradeHarness/.env.example`
- Create: `TradeHarness/tradeharness/__init__.py`

- [ ] **Step 1: Add dependency manifest**

```txt
requests==2.32.3
python-dotenv==1.0.1
```

- [ ] **Step 2: Add example environment file**

```dotenv
BINANCE_API_KEY=your_binance_testnet_key
BINANCE_API_SECRET=your_binance_testnet_secret
LMSTUDIO_BASE_URL=http://192.168.10.17:1234/v1
LMSTUDIO_MODEL=google/gemma-4-e2b
SYMBOL=BTCUSDT
POLL_INTERVAL_SECONDS=30
CANDLE_INTERVAL=1m
CANDLE_LIMIT=5
TRADE_SIZE_PERCENT=10
DRY_RUN=true
```

- [ ] **Step 3: Add package marker**

```python
"""Minimal Binance Futures Testnet bridge for LM Studio."""
```

- [ ] **Step 4: Smoke-check dependency installation path**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m pip install -r requirements.txt
```

Expected: `requests` and `python-dotenv` install without import errors.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .env.example tradeharness/__init__.py
git commit -m "chore: scaffold trade bridge project"
```

### Task 2: Define config and shared models

**Files:**
- Create: `TradeHarness/tradeharness/config.py`
- Create: `TradeHarness/tradeharness/models.py`

- [ ] **Step 1: Add runtime config loader**

```python
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


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


def load_settings() -> Settings:
    load_dotenv()
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
```

- [ ] **Step 2: Add shared data models**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Action = Literal["BUY", "SELL", "HOLD", "CLOSE"]


@dataclass(frozen=True)
class Candle:
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: float
    entry_price: float

    @property
    def is_open(self) -> bool:
        return self.quantity != 0.0

    @property
    def side(self) -> str:
        if self.quantity > 0:
            return "LONG"
        if self.quantity < 0:
            return "SHORT"
        return "FLAT"


@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str


@dataclass(frozen=True)
class SymbolFilters:
    step_size: float
    min_qty: float
```

- [ ] **Step 3: Smoke-check imports**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -c "from tradeharness.config import load_settings; from tradeharness.models import Decision, Position"
```

Expected: command exits without traceback.

- [ ] **Step 4: Commit**

```bash
git add tradeharness/config.py tradeharness/models.py
git commit -m "feat: add config and shared models"
```

### Task 3: Implement Binance Futures Testnet client

**Files:**
- Create: `TradeHarness/tradeharness/binance_client.py`

- [ ] **Step 1: Add signed REST client**

```python
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

import requests

from tradeharness.models import Candle, Position, SymbolFilters


class BinanceFuturesTestnetClient:
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://testnet.binancefuture.com") -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": self.api_key})

    def _sign_params(self, params: dict[str, Any]) -> dict[str, Any]:
        signed = dict(params)
        signed["timestamp"] = int(time.time() * 1000)
        query = urlencode(signed, doseq=True)
        signature = hmac.new(self.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        signed["signature"] = signature
        return signed

    def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None, signed: bool = False) -> Any:
        payload = params or {}
        if signed:
            payload = self._sign_params(payload)
        response = self.session.request(method, f"{self.base_url}{path}", params=payload, timeout=30)
        response.raise_for_status()
        return response.json()

    def get_price(self, symbol: str) -> float:
        data = self._request("GET", "/fapi/v1/ticker/price", params={"symbol": symbol})
        return float(data["price"])

    def get_klines(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        data = self._request("GET", "/fapi/v1/klines", params={"symbol": symbol, "interval": interval, "limit": limit})
        return [
            Candle(
                open_time=int(item[0]),
                open=float(item[1]),
                high=float(item[2]),
                low=float(item[3]),
                close=float(item[4]),
                volume=float(item[5]),
            )
            for item in data
        ]

    def get_available_balance(self, asset: str = "USDT") -> float:
        balances = self._request("GET", "/fapi/v2/balance", signed=True)
        for item in balances:
            if item["asset"] == asset:
                return float(item["availableBalance"])
        raise ValueError(f"Asset not found: {asset}")

    def get_position(self, symbol: str) -> Position:
        positions = self._request("GET", "/fapi/v2/positionRisk", signed=True)
        for item in positions:
            if item["symbol"] == symbol:
                return Position(
                    symbol=symbol,
                    quantity=float(item["positionAmt"]),
                    entry_price=float(item["entryPrice"]),
                )
        return Position(symbol=symbol, quantity=0.0, entry_price=0.0)

    def get_symbol_filters(self, symbol: str) -> SymbolFilters:
        data = self._request("GET", "/fapi/v1/exchangeInfo")
        for item in data["symbols"]:
            if item["symbol"] == symbol:
                lot_size = next(f for f in item["filters"] if f["filterType"] == "LOT_SIZE")
                return SymbolFilters(step_size=float(lot_size["stepSize"]), min_qty=float(lot_size["minQty"]))
        raise ValueError(f"Symbol not found: {symbol}")

    def place_market_order(self, symbol: str, side: str, quantity: float, reduce_only: bool = False) -> Any:
        params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": quantity,
        }
        if reduce_only:
            params["reduceOnly"] = "true"
        return self._request("POST", "/fapi/v1/order", params=params, signed=True)
```

- [ ] **Step 2: Smoke-check public market data call**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -c "from tradeharness.binance_client import BinanceFuturesTestnetClient as C; c=C('x','y'); print(type(c.get_price('BTCUSDT')).__name__)"
```

Expected: prints `float`.

- [ ] **Step 3: Commit**

```bash
git add tradeharness/binance_client.py
git commit -m "feat: add binance futures testnet client"
```

### Task 4: Implement LM Studio client and decision parser

**Files:**
- Create: `TradeHarness/tradeharness/llm_client.py`
- Create: `TradeHarness/tradeharness/decision_engine.py`

- [ ] **Step 1: Add LM Studio chat client**

```python
from __future__ import annotations

import requests


class LMStudioClient:
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def chat(self, prompt: str) -> str:
        response = requests.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "Return strict JSON only."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
```

- [ ] **Step 2: Add decision prompt builder and parser**

```python
from __future__ import annotations

import json

from tradeharness.models import Candle, Decision, Position


def build_prompt(symbol: str, price: float, candles: list[Candle], position: Position) -> str:
    candle_lines = [
        f"- open={c.open} high={c.high} low={c.low} close={c.close} volume={c.volume}"
        for c in candles
    ]
    return "\n".join(
        [
            f"You are deciding one action for {symbol} futures testnet.",
            "Allowed actions: BUY, SELL, HOLD, CLOSE.",
            "Return JSON with keys action and reason.",
            f"Current price: {price}",
            f"Current position side: {position.side}",
            "Recent candles:",
            *candle_lines,
        ]
    )


def parse_decision(raw_content: str) -> Decision:
    payload = json.loads(raw_content)
    action = str(payload["action"]).upper()
    if action not in {"BUY", "SELL", "HOLD", "CLOSE"}:
        raise ValueError(f"Unsupported action: {action}")
    reason = str(payload.get("reason", "")).strip()
    return Decision(action=action, reason=reason)
```

- [ ] **Step 3: Smoke-check parser path**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -c "from tradeharness.decision_engine import parse_decision; print(parse_decision('{\"action\":\"BUY\",\"reason\":\"test\"}').action)"
```

Expected: prints `BUY`.

- [ ] **Step 4: Commit**

```bash
git add tradeharness/llm_client.py tradeharness/decision_engine.py
git commit -m "feat: add lm studio decision flow"
```

### Task 5: Implement trading orchestration

**Files:**
- Create: `TradeHarness/tradeharness/trader.py`

- [ ] **Step 1: Add quantity rounding and percent-balance sizing**

```python
from __future__ import annotations

import math

from tradeharness.models import Decision, Position, SymbolFilters


def floor_to_step(value: float, step: float) -> float:
    precision = int(round(-math.log10(step), 0)) if step < 1 else 0
    floored = math.floor(value / step) * step
    return round(floored, precision)


def calculate_order_quantity(balance_usdt: float, trade_size_percent: float, price: float, filters: SymbolFilters) -> float:
    notional = balance_usdt * (trade_size_percent / 100.0)
    raw_quantity = notional / price
    quantity = floor_to_step(raw_quantity, filters.step_size)
    if quantity < filters.min_qty:
        raise ValueError("Calculated quantity is below exchange minimum.")
    return quantity


def map_decision_to_order(decision: Decision, position: Position) -> tuple[str, str, bool] | None:
    if decision.action == "HOLD":
        return None
    if decision.action == "BUY" and not position.is_open:
        return ("BUY", "open_long", False)
    if decision.action == "SELL" and not position.is_open:
        return ("SELL", "open_short", False)
    if decision.action == "CLOSE" and position.is_open:
        side = "SELL" if position.quantity > 0 else "BUY"
        return (side, "close_position", True)
    return None
```

- [ ] **Step 2: Smoke-check sizing helper**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -c "from tradeharness.models import SymbolFilters; from tradeharness.trader import calculate_order_quantity; print(calculate_order_quantity(1000, 10, 50000, SymbolFilters(step_size=0.001, min_qty=0.001)))"
```

Expected: prints a positive BTC quantity such as `0.002`.

- [ ] **Step 3: Commit**

```bash
git add tradeharness/trader.py
git commit -m "feat: add trading sizing and action mapping"
```

### Task 6: Wire the polling worker entrypoint

**Files:**
- Create: `TradeHarness/tradeharness/main.py`

- [ ] **Step 1: Add main loop and orchestration**

```python
from __future__ import annotations

import time

from tradeharness.binance_client import BinanceFuturesTestnetClient
from tradeharness.config import load_settings
from tradeharness.decision_engine import build_prompt, parse_decision
from tradeharness.llm_client import LMStudioClient
from tradeharness.trader import calculate_order_quantity, map_decision_to_order


def run_once() -> None:
    settings = load_settings()
    binance = BinanceFuturesTestnetClient(settings.binance_api_key, settings.binance_api_secret)
    llm = LMStudioClient(settings.lmstudio_base_url, settings.lmstudio_model)

    price = binance.get_price(settings.symbol)
    candles = binance.get_klines(settings.symbol, settings.candle_interval, settings.candle_limit)
    balance = binance.get_available_balance()
    position = binance.get_position(settings.symbol)
    filters = binance.get_symbol_filters(settings.symbol)

    prompt = build_prompt(settings.symbol, price, candles, position)
    raw_decision = llm.chat(prompt)
    decision = parse_decision(raw_decision)
    mapped = map_decision_to_order(decision, position)

    print(f"price={price} action={decision.action} reason={decision.reason} position={position.side}")

    if mapped is None:
        print("no_order_sent")
        return

    side, mode, reduce_only = mapped
    quantity = abs(position.quantity) if reduce_only else calculate_order_quantity(
        balance,
        settings.trade_size_percent,
        price,
        filters,
    )

    if settings.dry_run:
        print(f"dry_run side={side} quantity={quantity} mode={mode}")
        return

    result = binance.place_market_order(settings.symbol, side, quantity, reduce_only=reduce_only)
    print(f"order_sent mode={mode} response={result}")


def main() -> None:
    settings = load_settings()
    while True:
        run_once()
        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-check entrypoint import**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m tradeharness.main
```

Expected: in `DRY_RUN=true`, the worker starts, prints a cycle result, and waits for the next poll.

- [ ] **Step 3: Commit**

```bash
git add tradeharness/main.py
git commit -m "feat: wire polling trade worker"
```

### Task 7: Document local setup and run flow

**Files:**
- Modify: `TradeHarness/README.MD`

- [ ] **Step 1: Replace empty README with setup instructions**

```md
# TradeHarness

Minimal local bridge between LM Studio and Binance Futures Testnet for `BTCUSDT`.

## What It Does

- polls Binance Futures Testnet
- sends current price and recent candles to LM Studio
- expects one action: `BUY`, `SELL`, `HOLD`, or `CLOSE`
- optionally places a demo futures order

## Setup

```bash
cd /Users/atif/Public/TradeHarness
python3 -m pip install -r requirements.txt
cp .env.example .env
```

Fill in:

- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`

LM Studio defaults:

- URL: `http://192.168.10.17:1234/v1`
- Model: `google/gemma-4-e2b`

## Run

Dry run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m tradeharness.main
```

Real demo order mode:

Set `DRY_RUN=false` in `.env`, then run the same command.
```

- [ ] **Step 2: Smoke-check README commands**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m compileall tradeharness
```

Expected: Python modules compile without syntax errors.

- [ ] **Step 3: Commit**

```bash
git add README.MD
git commit -m "docs: add trade bridge setup guide"
```

## Self-Review

- Spec coverage check:
  - local Python polling worker: covered by Task 6
  - Binance market data and order execution: covered by Task 3 and Task 6
  - LM Studio OpenAI-compatible call: covered by Task 4
  - action set `BUY | SELL | HOLD | CLOSE`: covered by Task 4 and Task 5
  - percent-balance sizing: covered by Task 5
  - `.env.example` and README: covered by Task 1 and Task 7
- Placeholder scan: no `TODO`, `TBD`, or deferred implementation placeholders remain.
- Type consistency: `Decision`, `Position`, `SymbolFilters`, `calculate_order_quantity`, and `map_decision_to_order` are named consistently across tasks.
