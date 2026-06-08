# Agent Architecture Folder Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the `TradeHarness` package into capability-based folders that match the current agent architecture without changing runtime behavior.

**Architecture:** The refactor moves low-level exchange and LM Studio code into `integrations`, shared contracts into `domain`, settings into `config`, orchestration into `runtime`, and agent-exposed actions into `tools`. A thin compatibility entrypoint preserves `python3 -m tradeharness.main` while imports are updated to the new structure.

**Tech Stack:** Python 3, `requests`, `unittest`, `compileall`

---

## File Structure

- Create: `TradeHarness/tradeharness/config/__init__.py`
- Create: `TradeHarness/tradeharness/config/settings.py`
- Create: `TradeHarness/tradeharness/domain/__init__.py`
- Create: `TradeHarness/tradeharness/domain/models.py`
- Create: `TradeHarness/tradeharness/integrations/__init__.py`
- Create: `TradeHarness/tradeharness/integrations/binance/__init__.py`
- Create: `TradeHarness/tradeharness/integrations/binance/client.py`
- Create: `TradeHarness/tradeharness/integrations/lmstudio/__init__.py`
- Create: `TradeHarness/tradeharness/integrations/lmstudio/client.py`
- Create: `TradeHarness/tradeharness/runtime/__init__.py`
- Create: `TradeHarness/tradeharness/runtime/agent.py`
- Create: `TradeHarness/tradeharness/runtime/main.py`
- Create: `TradeHarness/tradeharness/tools/__init__.py`
- Create: `TradeHarness/tradeharness/tools/binance.py`
- Modify: `TradeHarness/tradeharness/main.py`
- Modify: `TradeHarness/tests/test_agent_tools.py`
- Modify: `TradeHarness/README.MD`
- Delete: `TradeHarness/tradeharness/config.py`
- Delete: `TradeHarness/tradeharness/models.py`
- Delete: `TradeHarness/tradeharness/binance_client.py`
- Delete: `TradeHarness/tradeharness/llm_client.py`
- Delete: `TradeHarness/tradeharness/binance_tools.py`
- Delete: `TradeHarness/tradeharness/agent_runtime.py`
- Delete: `TradeHarness/tradeharness/decision_engine.py`

## Implementation Notes

- Preserve behavior first. This is a file-structure refactor, not a feature rewrite.
- Keep the current tool names, runtime prompt, and dry-run behavior unchanged.
- Preserve the current unit tests conceptually, but update imports to the new paths.
- Keep `tradeharness/main.py` as a compatibility wrapper so the existing run command still works.

### Task 1: Move settings and domain contracts into dedicated folders

**Files:**
- Create: `TradeHarness/tradeharness/config/__init__.py`
- Create: `TradeHarness/tradeharness/config/settings.py`
- Create: `TradeHarness/tradeharness/domain/__init__.py`
- Create: `TradeHarness/tradeharness/domain/models.py`
- Modify: `TradeHarness/tests/test_agent_tools.py`
- Delete: `TradeHarness/tradeharness/config.py`
- Delete: `TradeHarness/tradeharness/models.py`

- [ ] **Step 1: Write the failing import-path test update**

```python
from tradeharness.domain.models import ToolRequest
from tradeharness.config.settings import load_settings
```

Apply that import-path expectation in `tests/test_agent_tools.py` by replacing old top-level module imports with:

```python
from tradeharness.tools.binance import BinanceToolset
from tradeharness.integrations.lmstudio.client import extract_tool_requests
```

- [ ] **Step 2: Run tests to verify they fail on missing modules**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: `ModuleNotFoundError` for one or more of `tradeharness.tools.binance`, `tradeharness.integrations.lmstudio.client`, `tradeharness.domain.models`, or `tradeharness.config.settings`.

- [ ] **Step 3: Create `config` package**

`tradeharness/config/__init__.py`

```python
from tradeharness.config.settings import Settings, load_settings

__all__ = ["Settings", "load_settings"]
```

`tradeharness/config/settings.py`

```python
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
```

- [ ] **Step 4: Create `domain` package**

`tradeharness/domain/__init__.py`

```python
from tradeharness.domain.models import Candle, Decision, Position, SymbolFilters, ToolRequest

__all__ = ["Candle", "Decision", "Position", "SymbolFilters", "ToolRequest"]
```

`tradeharness/domain/models.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


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


@dataclass(frozen=True)
class ToolRequest:
    name: str
    arguments: dict[str, Any]
    call_id: str | None = None
```

- [ ] **Step 5: Delete old flat files**

Delete:

```text
tradeharness/config.py
tradeharness/models.py
```

- [ ] **Step 6: Run tests to verify the new package paths pass**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: tests either pass or now fail only on the next missing moved module path.

### Task 2: Move low-level integrations into `integrations/binance` and `integrations/lmstudio`

**Files:**
- Create: `TradeHarness/tradeharness/integrations/__init__.py`
- Create: `TradeHarness/tradeharness/integrations/binance/__init__.py`
- Create: `TradeHarness/tradeharness/integrations/binance/client.py`
- Create: `TradeHarness/tradeharness/integrations/lmstudio/__init__.py`
- Create: `TradeHarness/tradeharness/integrations/lmstudio/client.py`
- Delete: `TradeHarness/tradeharness/binance_client.py`
- Delete: `TradeHarness/tradeharness/llm_client.py`
- Delete: `TradeHarness/tradeharness/decision_engine.py`

- [ ] **Step 1: Write the failing test import update for integrations**

Update `tests/test_agent_tools.py` to use:

```python
from tradeharness.integrations.lmstudio.client import extract_tool_requests
```

Keep the test content unchanged otherwise.

- [ ] **Step 2: Run tests to verify they fail on missing integration modules**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: `ModuleNotFoundError` for `tradeharness.integrations.lmstudio.client` and possibly `tradeharness.tools.binance`.

- [ ] **Step 3: Create integration package markers**

`tradeharness/integrations/__init__.py`

```python
"""External system integrations."""
```

`tradeharness/integrations/binance/__init__.py`

```python
from tradeharness.integrations.binance.client import BinanceFuturesTestnetClient

__all__ = ["BinanceFuturesTestnetClient"]
```

`tradeharness/integrations/lmstudio/__init__.py`

```python
from tradeharness.integrations.lmstudio.client import (
    LMStudioClient,
    extract_tool_requests,
    get_message_content,
)

__all__ = ["LMStudioClient", "extract_tool_requests", "get_message_content"]
```

- [ ] **Step 4: Move Binance client into integration folder**

Create `tradeharness/integrations/binance/client.py` with:

```python
from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

import requests

from tradeharness.domain.models import Candle, Position, SymbolFilters


class BinanceFuturesTestnetClient:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "https://testnet.binancefuture.com",
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"X-MBX-APIKEY": self.api_key})

    def _sign_params(self, params: dict[str, Any]) -> dict[str, Any]:
        signed = dict(params)
        signed["timestamp"] = int(time.time() * 1000)
        query = urlencode(signed, doseq=True)
        signature = hmac.new(
            self.api_secret.encode(),
            query.encode(),
            hashlib.sha256,
        ).hexdigest()
        signed["signature"] = signature
        return signed

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        signed: bool = False,
    ) -> Any:
        payload = params or {}
        if signed:
            payload = self._sign_params(payload)
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            params=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def get_price(self, symbol: str) -> float:
        data = self._request("GET", "/fapi/v1/ticker/price", params={"symbol": symbol})
        return float(data["price"])

    def get_klines(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        data = self._request(
            "GET",
            "/fapi/v1/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
        )
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
                lot_size = next(
                    filter_item
                    for filter_item in item["filters"]
                    if filter_item["filterType"] == "LOT_SIZE"
                )
                return SymbolFilters(
                    step_size=float(lot_size["stepSize"]),
                    min_qty=float(lot_size["minQty"]),
                )
        raise ValueError(f"Symbol not found: {symbol}")

    def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        reduce_only: bool = False,
    ) -> Any:
        params: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": quantity,
        }
        if reduce_only:
            params["reduceOnly"] = "true"
        return self._request("POST", "/fapi/v1/order", params=params, signed=True)
```

- [ ] **Step 5: Move LM Studio client and decision-engine responsibilities into integration folder**

Create `tradeharness/integrations/lmstudio/client.py` with:

```python
from __future__ import annotations

import json
from typing import Any

import requests

from tradeharness.domain.models import ToolRequest


class LMStudioClient:
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        response = requests.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def chat(self, prompt: str) -> str:
        response = self.complete(
            [
                {"role": "system", "content": "Return strict JSON only."},
                {"role": "user", "content": prompt},
            ]
        )
        return get_message_content(response)


def get_message_content(response: dict[str, Any]) -> str:
    return str(response["choices"][0]["message"].get("content", ""))


def extract_tool_requests(response: dict[str, Any]) -> list[ToolRequest]:
    message = response["choices"][0]["message"]
    native_tool_calls = message.get("tool_calls") or []
    if native_tool_calls:
        requests_out: list[ToolRequest] = []
        for tool_call in native_tool_calls:
            function = tool_call["function"]
            requests_out.append(
                ToolRequest(
                    name=str(function["name"]),
                    arguments=json.loads(function["arguments"]),
                    call_id=str(tool_call.get("id")) if tool_call.get("id") else None,
                )
            )
        return requests_out

    content = _strip_code_fences(str(message.get("content", "")).strip())
    if not content:
        return []
    payload = json.loads(content)
    if "tool" not in payload:
        return []
    return [
        ToolRequest(
            name=str(payload["tool"]),
            arguments=dict(payload.get("arguments", {})),
        )
    ]


def _strip_code_fences(content: str) -> str:
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return content
```

- [ ] **Step 6: Delete old flat integration files**

Delete:

```text
tradeharness/binance_client.py
tradeharness/llm_client.py
tradeharness/decision_engine.py
```

- [ ] **Step 7: Run tests to verify tool-request extraction still passes**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: extraction tests pass, or any remaining failures point only to the next missing moved tool/runtime module.

### Task 3: Move Binance tool behavior into `tools/binance.py`

**Files:**
- Create: `TradeHarness/tradeharness/tools/__init__.py`
- Create: `TradeHarness/tradeharness/tools/binance.py`
- Delete: `TradeHarness/tradeharness/binance_tools.py`
- Modify: `TradeHarness/tests/test_agent_tools.py`

- [ ] **Step 1: Write the failing test import update for tools**

Ensure `tests/test_agent_tools.py` imports:

```python
from tradeharness.tools.binance import BinanceToolset
```

- [ ] **Step 2: Run tests to verify they fail on missing `tools/binance.py`**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: `ModuleNotFoundError` for `tradeharness.tools.binance`.

- [ ] **Step 3: Create tool package markers**

`tradeharness/tools/__init__.py`

```python
from tradeharness.tools.binance import BinanceToolset

__all__ = ["BinanceToolset"]
```

- [ ] **Step 4: Move Binance tool behavior into `tools/binance.py`**

Create `tradeharness/tools/binance.py` with:

```python
from __future__ import annotations

from typing import Any

from tradeharness.integrations.binance.client import BinanceFuturesTestnetClient


def calculate_order_quantity(
    balance_usdt: float,
    trade_size_percent: float,
    price: float,
    step_size: float,
    min_qty: float,
) -> float:
    raw_quantity = (balance_usdt * (trade_size_percent / 100.0)) / price
    precision = 0
    if step_size < 1:
        step_text = f"{step_size:.12f}".rstrip("0")
        precision = len(step_text.split(".")[1]) if "." in step_text else 0
    scaled = int(raw_quantity / step_size) * step_size
    quantity = round(scaled, precision)
    if quantity < min_qty:
        raise ValueError("Calculated quantity is below exchange minimum.")
    return quantity


class BinanceToolset:
    def __init__(
        self,
        client: BinanceFuturesTestnetClient,
        trade_size_percent: float,
        dry_run: bool = False,
    ) -> None:
        self.client = client
        self.trade_size_percent = trade_size_percent
        self.dry_run = dry_run

    def definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_market_snapshot",
                    "description": "Get current market snapshot for a symbol including latest price and recent candles.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string"},
                            "interval": {"type": "string"},
                            "limit": {"type": "integer"},
                        },
                        "required": ["symbol", "interval", "limit"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_balance",
                    "description": "Get available futures balance for an asset.",
                    "parameters": {
                        "type": "object",
                        "properties": {"asset": {"type": "string"}},
                        "required": ["asset"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_position",
                    "description": "Get current futures position for a symbol.",
                    "parameters": {
                        "type": "object",
                        "properties": {"symbol": {"type": "string"}},
                        "required": ["symbol"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "open_long",
                    "description": "Open a long futures position using configured percent-of-balance sizing.",
                    "parameters": {
                        "type": "object",
                        "properties": {"symbol": {"type": "string"}},
                        "required": ["symbol"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "open_short",
                    "description": "Open a short futures position using configured percent-of-balance sizing.",
                    "parameters": {
                        "type": "object",
                        "properties": {"symbol": {"type": "string"}},
                        "required": ["symbol"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "close_position",
                    "description": "Close the current open futures position for a symbol.",
                    "parameters": {
                        "type": "object",
                        "properties": {"symbol": {"type": "string"}},
                        "required": ["symbol"],
                    },
                },
            },
        ]

    def run_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "get_market_snapshot":
            return self._get_market_snapshot(
                symbol=str(arguments["symbol"]),
                interval=str(arguments["interval"]),
                limit=int(arguments["limit"]),
            )
        if name == "get_balance":
            return self._get_balance(asset=str(arguments.get("asset", "USDT")))
        if name == "get_position":
            return self._get_position(symbol=str(arguments["symbol"]))
        if name == "open_long":
            return self._open_directional_position(symbol=str(arguments["symbol"]), side="BUY")
        if name == "open_short":
            return self._open_directional_position(symbol=str(arguments["symbol"]), side="SELL")
        if name == "close_position":
            return self._close_position(symbol=str(arguments["symbol"]))
        raise ValueError(f"Unsupported tool: {name}")

    def _get_market_snapshot(self, symbol: str, interval: str, limit: int) -> dict[str, Any]:
        candles = self.client.get_klines(symbol, interval, limit)
        return {
            "symbol": symbol,
            "price": self.client.get_price(symbol),
            "interval": interval,
            "candles": [
                {
                    "open_time": candle.open_time,
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume,
                }
                for candle in candles
            ],
        }

    def _get_balance(self, asset: str) -> dict[str, Any]:
        normalized_asset = self._normalize_asset(asset)
        return {
            "asset": normalized_asset,
            "available_balance": self.client.get_available_balance(normalized_asset),
        }

    def _get_position(self, symbol: str) -> dict[str, Any]:
        position = self.client.get_position(symbol)
        return {
            "symbol": symbol,
            "quantity": position.quantity,
            "entry_price": position.entry_price,
            "side": position.side,
            "is_open": position.is_open,
        }

    def _open_directional_position(self, symbol: str, side: str) -> dict[str, Any]:
        balance = self.client.get_available_balance("USDT")
        price = self.client.get_price(symbol)
        filters = self.client.get_symbol_filters(symbol)
        quantity = calculate_order_quantity(
            balance,
            self.trade_size_percent,
            price,
            filters.step_size,
            filters.min_qty,
        )
        if self.dry_run:
            return {
                "status": "dry_run",
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
            }
        result = self.client.place_market_order(symbol, side, quantity, reduce_only=False)
        return {
            "status": "submitted",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "exchange_response": result,
        }

    def _close_position(self, symbol: str) -> dict[str, Any]:
        position = self.client.get_position(symbol)
        if not position.is_open:
            return {"status": "noop", "symbol": symbol, "reason": "No open position"}
        side = "SELL" if position.quantity > 0 else "BUY"
        quantity = abs(position.quantity)
        if self.dry_run:
            return {
                "status": "dry_run",
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "reduce_only": True,
            }
        result = self.client.place_market_order(symbol, side, quantity, reduce_only=True)
        return {
            "status": "submitted",
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "reduce_only": True,
            "exchange_response": result,
        }

    def _normalize_asset(self, asset: str) -> str:
        upper = asset.upper()
        if upper.endswith("USDT"):
            return "USDT"
        return upper
```

- [ ] **Step 5: Delete old flat tool file**

Delete:

```text
tradeharness/binance_tools.py
```

- [ ] **Step 6: Run tests to verify tool behavior still passes**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
```

Expected: all existing tool extraction and Binance tool dispatch tests pass.

### Task 4: Move orchestration into `runtime` and preserve top-level entrypoint

**Files:**
- Create: `TradeHarness/tradeharness/runtime/__init__.py`
- Create: `TradeHarness/tradeharness/runtime/agent.py`
- Create: `TradeHarness/tradeharness/runtime/main.py`
- Modify: `TradeHarness/tradeharness/main.py`
- Delete: `TradeHarness/tradeharness/agent_runtime.py`

- [ ] **Step 1: Create runtime package marker**

`tradeharness/runtime/__init__.py`

```python
from tradeharness.runtime.agent import run_agent_cycle
from tradeharness.runtime.main import main, run_once

__all__ = ["main", "run_agent_cycle", "run_once"]
```

- [ ] **Step 2: Move agent loop into `runtime/agent.py`**

Create `tradeharness/runtime/agent.py` with:

```python
from __future__ import annotations

import json
from typing import Any

from tradeharness.config.settings import Settings
from tradeharness.integrations.binance.client import BinanceFuturesTestnetClient
from tradeharness.integrations.lmstudio.client import (
    LMStudioClient,
    extract_tool_requests,
    get_message_content,
)
from tradeharness.tools.binance import BinanceToolset

SYSTEM_PROMPT = """You are a BTCUSDT Binance Futures Testnet trading agent.
Your brain runs in LM Studio. Your only way to inspect or act on Binance is through the provided tools.

Rules:
- Use tools to inspect market state, balance, and position before trading.
- Prefer get_market_snapshot, get_balance, and get_position before open_long, open_short, or close_position.
- If native tool calling is unavailable, return strict JSON like {"tool":"get_market_snapshot","arguments":{"symbol":"BTCUSDT","interval":"1m","limit":5}}.
- When you are done and no more tool calls are needed, return strict JSON like {"final":"short operator summary"}.
- Never mention tools that do not exist.
"""


def run_agent_cycle(settings: Settings) -> None:
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

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
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
            for tool_request in tool_requests:
                tool_result = toolset.run_tool(tool_request.name, tool_request.arguments)
                print(f"tool={tool_request.name} result={json.dumps(tool_result)}")
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
            continue

        content = get_message_content(response).strip()
        if content:
            print(f"agent={content}")
        return

    print('agent={"final":"max tool steps reached"}')
```

- [ ] **Step 3: Move runtime entrypoint into `runtime/main.py`**

Create `tradeharness/runtime/main.py` with:

```python
from __future__ import annotations

import time

from tradeharness.config.settings import load_settings
from tradeharness.runtime.agent import run_agent_cycle


def run_once() -> None:
    settings = load_settings()
    run_agent_cycle(settings)


def main() -> None:
    settings = load_settings()
    while True:
        run_once()
        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Convert top-level `tradeharness/main.py` into a compatibility wrapper**

Replace `tradeharness/main.py` with:

```python
from tradeharness.runtime.main import main, run_once

__all__ = ["main", "run_once"]


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Delete old flat runtime file**

Delete:

```text
tradeharness/agent_runtime.py
```

- [ ] **Step 6: Run compile and test verification**

Run:

```bash
cd /Users/atif/Public/TradeHarness
python3 -m unittest tests/test_agent_tools.py -v
python3 -m compileall tradeharness tests
```

Expected: tests pass and compile output has no syntax errors.

### Task 5: Update docs and verify the current dry-run command still works

**Files:**
- Modify: `TradeHarness/README.MD`

- [ ] **Step 1: Update README package path explanation**

Add a short architecture section below the intro:

```md
## Package Layout

- `tradeharness/config/`: runtime settings
- `tradeharness/domain/`: shared data contracts
- `tradeharness/integrations/binance/`: low-level Binance client
- `tradeharness/integrations/lmstudio/`: LM Studio client and tool-request parsing
- `tradeharness/tools/`: Binance tools exposed to the agent
- `tradeharness/runtime/`: agent orchestration loop
```

Keep the existing setup and run commands unchanged.

- [ ] **Step 2: Run the current dry-run command through the compatibility entrypoint**

Run:

```bash
cd /Users/atif/Public/TradeHarness
DRY_RUN=true python3 - <<'PY'
from tradeharness.main import run_once
run_once()
PY
```

Expected:
- at least one `tool=` line prints from the runtime
- a final `agent=` line prints
- no real order is submitted because `DRY_RUN=true`

- [ ] **Step 3: Commit**

```bash
git add README.MD tradeharness tests
git commit -m "refactor: align package layout with agent architecture"
```

## Self-Review

- Spec coverage check:
  - capability-based folders: covered by Tasks 1-4
  - `decision_engine.py` absorbed into LM Studio integration: covered by Task 2
  - top-level run path preserved: covered by Task 4 and Task 5
  - tests, compile checks, and dry-run behavior preserved: covered by Tasks 3-5
- Placeholder scan: no `TODO`, `TBD`, or vague references remain.
- Type consistency: `Settings`, `ToolRequest`, `BinanceFuturesTestnetClient`, `LMStudioClient`, `BinanceToolset`, `run_agent_cycle`, `run_once`, and `main` are used consistently across tasks.
