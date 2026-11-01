"""Delta Exchange (India / Global) - REST API v2.

Docs: https://docs.delta.exchange
Delta par futures/perpetual contracts hote hain. Size "contracts" mein jaata hai,
jaise BTCUSD ka 1 contract = 0.001 BTC (contract_value API se aata hai).
Ye bot sirf LONG leta hai (buy -> sell), short nahi.
"""
import hashlib
import hmac
import json
import math
import time
from urllib.parse import urlencode

import pandas as pd

from .base import Exchange, ExchangeError, interval_timedelta, to_frame

URLS = {"india": "https://api.india.delta.exchange", "global": "https://api.delta.exchange"}
MAX_CANDLES_PER_CALL = 2000


class DeltaExchange(Exchange):
    name = "delta"
    quote_asset = "USD"
    default_fee_pct = 0.0006   # taker ~0.05% + GST; apne account ki fee check karo

    def __init__(self, region: str = "india", **kw):
        super().__init__(**kw)
        self.base = URLS[region]
        self.name = f"delta-{region}"
        self._products: dict[str, dict] = {}

    # ---------- signing ----------
    def _sign(self, method: str, path: str, query: str, body: str) -> dict:
        ts = str(int(time.time()))
        msg = method + ts + path + query + body
        sig = hmac.new(self.api_secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
        return {"api-key": self.api_key, "timestamp": ts, "signature": sig,
                "User-Agent": "apnasehore-bot", "Content-Type": "application/json"}

    def _request(self, method: str, path: str, params: dict | None = None,
                 body: dict | None = None, auth: bool = False):
        query = ("?" + urlencode(params)) if params else ""
        body_s = json.dumps(body, separators=(",", ":")) if body else ""
        headers = {"User-Agent": "apnasehore-bot", "Content-Type": "application/json"}
        if auth:
            self._require_keys()
            headers = self._sign(method, path, query, body_s)
        resp = self.session.request(method, self.base + path + query, data=body_s or None,
                                    headers=headers, timeout=self.timeout)
        return self._check(resp)["result"]

    # ---------- public ----------
    def product(self, symbol: str) -> dict:
        if symbol not in self._products:
            self._products[symbol] = self._request("GET", f"/v2/products/{symbol}")
        return self._products[symbol]

    def qty_step(self, symbol: str) -> float:
        return float(self.product(symbol)["contract_value"])

    def fetch_candles(self, symbol: str, interval: str = "1d", limit: int = 500) -> pd.DataFrame:
        step = interval_timedelta(interval)
        end = int(time.time())
        start = end - int(step.total_seconds()) * limit
        rows, cur = [], start
        while cur < end:  # 2000 candles se zyada ho to tukdon mein lo
            chunk_end = min(end, cur + int(step.total_seconds()) * MAX_CANDLES_PER_CALL)
            rows += self._request("GET", "/v2/history/candles", params={
                "resolution": interval, "symbol": symbol, "start": cur, "end": chunk_end})
            cur = chunk_end
        return to_frame(rows, "time", "s")

    # ---------- private ----------
    def get_balance(self, asset: str | None = None) -> float:
        asset = asset or self.quote_asset
        for b in self._request("GET", "/v2/wallet/balances", auth=True):
            if b.get("asset_symbol") == asset:
                return float(b.get("available_balance", 0))
        return 0.0

    def contracts_for(self, symbol: str, qty: float) -> int:
        return math.floor(qty / self.qty_step(symbol) + 1e-9)

    def place_market_order(self, symbol: str, side: str, qty: float) -> dict:
        contracts = self.contracts_for(symbol, qty)
        if contracts < 1:
            raise ExchangeError(f"Quantity {qty} 1 contract se kam hai ({self.qty_step(symbol)}).")
        body = {"product_id": self.product(symbol)["id"], "size": contracts,
                "side": side, "order_type": "market_order"}
        if side == "sell":
            body["reduce_only"] = True   # sirf position band kare, galti se short na khule
        return self._request("POST", "/v2/orders", body=body, auth=True)
