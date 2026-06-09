from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

import requests

from tradeharness.domain.models import Candle, Position, SymbolFilters


class BinanceAPIError(RuntimeError):
    def __init__(
        self,
        *,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
        url: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.response_body = response_body
        self.url = url
        super().__init__(message)


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
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            response_body = ""
            try:
                response_body = response.text
            except Exception:
                response_body = ""
            detail = response_body.strip() or str(exc)
            raise BinanceAPIError(
                message=(
                    f"Binance API request failed: {method} {path} "
                    f"status={response.status_code} detail={detail}"
                ),
                status_code=response.status_code,
                response_body=response_body,
                url=getattr(response, "url", None),
            ) from exc
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
