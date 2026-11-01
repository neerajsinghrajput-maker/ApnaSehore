"""Exchange adapters ko bina internet test karna (nakli HTTP responses)."""
import hashlib
import hmac
import json
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest

from bot.exchanges.base import ExchangeError
from bot.exchanges.coindcx import CoinDCX
from bot.exchanges.delta import DeltaExchange


class FakeResp:
    def __init__(self, data, status=200):
        self._d, self.status_code, self.text = data, status, json.dumps(data)

    def json(self):
        return self._d


class FakeSession:
    def __init__(self, router):
        self.router, self.calls = router, []

    def request(self, method, url, data=None, headers=None, params=None, timeout=None):
        self.calls.append({"method": method, "url": url, "data": data, "headers": headers or {}, "params": params})
        return FakeResp(*self.router(method, url, data, params))

    def get(self, url, params=None, timeout=None, headers=None):
        return self.request("GET", url, params=params, headers=headers)

    def post(self, url, data=None, headers=None, timeout=None):
        return self.request("POST", url, data=data, headers=headers)


# ---------------- Delta ----------------
def delta_router(method, url, data, params):
    u = urlparse(url)
    if u.path == "/v2/products/BTCUSD":
        return ({"success": True, "result": {"id": 27, "symbol": "BTCUSD", "contract_value": "0.001"}},)
    if u.path == "/v2/history/candles":
        q = parse_qs(u.query)
        start, end = int(q["start"][0]), int(q["end"][0])
        rows = [{"time": t, "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10}
                for t in range(start, end, 3600)]
        return ({"success": True, "result": rows},)
    if u.path == "/v2/wallet/balances":
        return ({"success": True, "result": [{"asset_symbol": "USD", "available_balance": "123.45"}]},)
    if u.path == "/v2/orders":
        return ({"success": True, "result": {"id": 999, **json.loads(data)}},)
    return ({"success": False, "error": {"code": "not_found"}}, 404)


def test_delta_candles_paginate_and_parse():
    s = FakeSession(delta_router)
    df = DeltaExchange(session=s).fetch_candles("BTCUSD", "1h", limit=4500)
    assert len(df) == 4500
    assert len([c for c in s.calls if "candles" in c["url"]]) == 3   # 2000 + 2000 + 500
    assert df.index.is_monotonic_increasing and str(df.index.tz) == "UTC"
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_delta_signed_order_in_contracts():
    s = FakeSession(delta_router)
    ex = DeltaExchange(session=s, api_key="k", api_secret="sec")
    assert ex.qty_step("BTCUSD") == 0.001
    res = ex.place_market_order("BTCUSD", "sell", 0.0057)
    body = json.loads(s.calls[-1]["data"])
    assert body == {"product_id": 27, "size": 5, "side": "sell", "order_type": "market_order", "reduce_only": True}
    assert res["id"] == 999
    h = s.calls[-1]["headers"]
    msg = "POST" + h["timestamp"] + "/v2/orders" + "" + s.calls[-1]["data"]
    assert h["signature"] == hmac.new(b"sec", msg.encode(), hashlib.sha256).hexdigest()
    assert h["api-key"] == "k"


def test_delta_balance_and_errors():
    ex = DeltaExchange(session=FakeSession(delta_router), api_key="k", api_secret="s")
    assert ex.get_balance() == 123.45
    with pytest.raises(ExchangeError):
        ex.place_market_order("BTCUSD", "buy", 0.0004)   # 1 contract se kam
    with pytest.raises(ExchangeError):
        DeltaExchange(session=FakeSession(delta_router)).get_balance()   # keys nahi


# ---------------- CoinDCX ----------------
MARKETS = [{"coindcx_name": "BTCINR", "pair": "I-BTC_INR", "target_currency_precision": 5,
            "base_currency_short_name": "INR", "target_currency_short_name": "BTC"}]


def dcx_router(method, url, data, params):
    if url.endswith("/exchange/v1/markets_details"):
        return (MARKETS,)
    if url.endswith("/market_data/candles"):
        assert params["pair"] == "I-BTC_INR"
        base = 1_700_000_000_000
        rows = [{"open": 1, "high": 2, "low": 0.5, "close": 1 + i, "volume": 5, "time": base + i * 86_400_000}
                for i in range(params["limit"])][::-1]   # CoinDCX nayi candle pehle deta hai
        return (rows,)
    if url.endswith("/users/balances"):
        return ([{"currency": "INR", "balance": "5000.5", "locked_balance": "0"}],)
    if url.endswith("/orders/create"):
        return ({"orders": [{"id": "abc"}]},)
    return ({"message": "not found"}, 404)


def test_coindcx_candles_sorted():
    df = CoinDCX(session=FakeSession(dcx_router)).fetch_candles("btcinr", "1d", limit=50)
    assert len(df) == 50 and df["Close"].iloc[-1] == 50 and df.index.is_monotonic_increasing


def test_coindcx_signed_order():
    s = FakeSession(dcx_router)
    ex = CoinDCX(session=s, api_key="k", api_secret="sec")
    assert ex.qty_step("BTCINR") == pytest.approx(0.00001)
    assert ex.get_balance() == 5000.5
    ex.place_market_order("BTCINR", "buy", 0.0012)
    call = s.calls[-1]
    body = json.loads(call["data"])
    assert body["market"] == "BTCINR" and body["total_quantity"] == 0.0012 and "timestamp" in body
    assert call["headers"]["X-AUTH-SIGNATURE"] == hmac.new(b"sec", call["data"].encode(), hashlib.sha256).hexdigest()


def test_coindcx_unknown_market():
    with pytest.raises(ExchangeError):
        CoinDCX(session=FakeSession(dcx_router)).fetch_candles("XYZINR")
