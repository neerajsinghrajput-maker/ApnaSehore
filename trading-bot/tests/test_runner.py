import os

import pandas as pd
import pytest

from bot.config import Config
from bot.exchanges.base import Exchange, ExchangeError
from bot.runner import run_once
from bot.engine import load_state


def crossover_frame(n_extra_up=10):
    """Flat, phir upar -> last closed candle par BUY crossover."""
    close = [100.0] * 60 + [100 + i for i in range(1, n_extra_up + 1)]
    idx = pd.date_range("2026-01-01", periods=len(close), freq="1h", tz="UTC")
    return pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close, "Volume": 1.0}, index=idx)


class FakeEx(Exchange):
    name, quote_asset = "fake", "INR"

    def __init__(self, df, balance=1e9):
        super().__init__(api_key="k", api_secret="s")
        self.df, self.balance, self.orders = df, balance, []

    def fetch_candles(self, symbol, interval="1d", limit=500):
        return self.df

    def qty_step(self, symbol):
        return 0.001

    def get_balance(self, asset=None):
        return self.balance

    def place_market_order(self, symbol, side, qty):
        self.orders.append((side, qty))
        return {"id": len(self.orders)}


CFG = dict(fast_ma=3, slow_ma=10, rsi_overbought=101, qty_step=0.001, starting_capital=10_000)


def first_buy_setup():
    df = crossover_frame(1)
    # chalti (forming) candle add karo -> ise ignore hona chahiye
    now = df.index[-1] + pd.Timedelta("1h") + pd.Timedelta("10min")
    forming = df.iloc[[-1]].copy(); forming.index = [df.index[-1] + pd.Timedelta("1h")]
    return pd.concat([df, forming]), now


def test_paper_buy_once_per_candle(tmp_path):
    df, now = first_buy_setup()
    ex, st = FakeEx(df), str(tmp_path / "s.json")
    cfg = Config(**CFG)
    e1 = run_once(ex, "BTCINR", "1h", cfg, st, now=now)
    assert e1["action"] == "BUY" and e1["mode"] == "PAPER" and ex.orders == []
    e2 = run_once(ex, "BTCINR", "1h", cfg, st, now=now)
    assert e2["action"] == "HOLD"   # same candle, dobara BUY nahi
    assert "BTCINR" in load_state(st, cfg)["positions"]


def test_stop_loss_exit(tmp_path):
    df, now = first_buy_setup()
    ex, st, cfg = FakeEx(df), str(tmp_path / "s.json"), Config(**CFG)
    run_once(ex, "BTCINR", "1h", cfg, st, now=now)
    crash = df.copy(); crash.iloc[-1, crash.columns.get_loc("Close")] = 50.0
    ex.df = crash
    e = run_once(ex, "BTCINR", "1h", cfg, st, now=now)
    assert e["action"] == "SELL" and e["reason"] == "stop_loss" and e["pnl"] < 0


def test_live_requires_gate(tmp_path, monkeypatch):
    df, now = first_buy_setup()
    monkeypatch.delenv("LIVE_TRADING", raising=False)
    with pytest.raises(SystemExit):
        run_once(FakeEx(df), "BTCINR", "1h", Config(**CFG, max_order_value=1000), str(tmp_path / "s"), live=True, now=now)
    monkeypatch.setenv("LIVE_TRADING", "YES")
    with pytest.raises(SystemExit):   # max_order_value missing
        run_once(FakeEx(df), "BTCINR", "1h", Config(**CFG), str(tmp_path / "s"), live=True, now=now)


def test_live_places_order_and_checks_balance(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_TRADING", "YES")
    df, now = first_buy_setup()
    cfg = Config(**CFG, max_order_value=1000)
    poor = FakeEx(df, balance=1)
    e = run_once(poor, "BTCINR", "1h", cfg, str(tmp_path / "a.json"), live=True, now=now)
    assert e["action"] == "ERROR" and poor.orders == []
    rich = FakeEx(df)
    e = run_once(rich, "BTCINR", "1h", cfg, str(tmp_path / "b.json"), live=True, now=now)
    assert e["action"] == "BUY" and rich.orders[0][0] == "buy"
    assert rich.orders[0][1] * df["Close"].iloc[-1] <= 1000   # max order cap


def test_kill_switch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "STOP").write_text("")
    df, now = first_buy_setup()
    e = run_once(FakeEx(df), "BTCINR", "1h", Config(**CFG), "s.json", now=now)
    assert e["action"] == "HOLD" and "KILL" in e["reason"]
