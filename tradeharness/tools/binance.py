from __future__ import annotations

from typing import Any

from tradeharness.integrations.binance.client import BinanceFuturesTestnetClient
from tradeharness.runtime.contracts.environment import augment_tool_description


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
                    "description": augment_tool_description(
                        "get_market_snapshot",
                        "Get current market snapshot for a symbol including latest price and recent candles.",
                    ),
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
                    "description": augment_tool_description(
                        "get_balance",
                        "Get available futures balance for an asset.",
                    ),
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
                    "description": augment_tool_description(
                        "get_position",
                        "Get current futures position for a symbol.",
                    ),
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
                    "description": augment_tool_description(
                        "open_long",
                        "Open a long futures position using configured percent-of-balance sizing.",
                    ),
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
                    "description": augment_tool_description(
                        "open_short",
                        "Open a short futures position using configured percent-of-balance sizing.",
                    ),
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
                    "description": augment_tool_description(
                        "close_position",
                        "Close the current open futures position for a symbol.",
                    ),
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
