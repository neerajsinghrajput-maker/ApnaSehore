"""CoinDCX - spot market REST API.

Docs: https://docs.coindcx.com
Market names: BTCINR, ETHINR, BTCUSDT ... (candles ke liye pair: I-BTC_INR, B-BTC_USDT)
"""
import hashlib
import hmac
import json
import time

import pandas as pd

from .base import Exchange, ExchangeError, to_frame

API = "https://api.coindcx.com"
PUBLIC = "https://public.coindcx.com"


class CoinDCX(Exchange):
    name = "coindcx"
    quote_asset = "INR"
    default_fee_pct = 0.005   # INR spot fee + GST ka conservative andaza; apni fee check karo

    def __init__(self, **kw):
        super().__init__(**kw)
        self._markets: dict[str, dict] | None = None

    # ---------- helpers ----------
    def markets(self) -> dict[str, dict]:
        if self._markets is None:
            resp = self.session.get(API + "/exchange/v1/markets_details", timeout=self.timeout)
            self._markets = {m["coindcx_name"]: m for m in self._check(resp)}
        return self._markets

    def market(self, symbol: str) -> dict:
        m = self.markets().get(symbol.upper())
        if not m:
            raise ExchangeError(f"CoinDCX par market {symbol} nahi mila (jaise BTCINR, ETHUSDT).")
        return m

    def _private(self, path: str, body: dict):
        self._require_keys()
        body = {**body, "timestamp": int(time.time() * 1000)}
        payload = json.dumps(body, separators=(",", ":"))
        sig = hmac.new(self.api_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        headers = {"Content-Type": "application/json", "X-AUTH-APIKEY": self.api_key,
                   "X-AUTH-SIGNATURE": sig}
        resp = self.session.post(API + path, data=payload, headers=headers, timeout=self.timeout)
        return self._check(resp)

    # ---------- public ----------
    def qty_step(self, symbol: str) -> float:
        m = self.market(symbol)
        if m.get("step"):
            return float(m["step"])
        return 10 ** -int(m.get("target_currency_precision", 4))

    def fetch_candles(self, symbol: str, interval: str = "1d", limit: int = 500) -> pd.DataFrame:
        pair = self.market(symbol)["pair"]
        resp = self.session.get(PUBLIC + "/market_data/candles", timeout=self.timeout,
                                params={"pair": pair, "interval": interval, "limit": min(limit, 1000)})
        return to_frame(self._check(resp), "time", "ms")

    # ---------- private ----------
    def get_balance(self, asset: str | None = None) -> float:
        asset = (asset or self.quote_asset).upper()
        for b in self._private("/exchange/v1/users/balances", {}):
            if b.get("currency", "").upper() == asset:
                return float(b.get("balance", 0))
        return 0.0

    def place_market_order(self, symbol: str, side: str, qty: float) -> dict:
        if qty <= 0:
            raise ExchangeError("Quantity 0 hai.")
        m = self.market(symbol)
        return self._private("/exchange/v1/orders/create", {
            "side": side, "order_type": "market_order", "market": m["coindcx_name"],
            "total_quantity": qty})
