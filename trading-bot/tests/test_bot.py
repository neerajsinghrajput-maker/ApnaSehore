import pandas as pd

from bot.backtest import run_backtest
from bot.config import Config
from bot.data import synthetic
from bot.indicators import rsi, sma
from bot.paper import paper_step
from bot.risk import position_size
from bot.strategy import BUY, SELL, generate_signals


def test_sma():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    assert sma(s, 3).iloc[-1] == 4.0


def test_rsi_all_up_is_100():
    s = pd.Series(range(1, 40), dtype=float)
    assert rsi(s, 14).iloc[-1] == 100.0


def test_position_size_respects_risk_and_cap():
    cfg = Config(risk_per_trade=0.01, stop_loss_pct=0.05, max_position_pct=0.25)
    # risk: 1000/(100*0.05)=200 shares; cap: 25000/100=250 -> 200
    assert position_size(100_000, 100, cfg) == 200
    # cap tighter: risk 1000/(100*0.01)=1000; cap 250 -> 250
    assert position_size(100_000, 100, Config(stop_loss_pct=0.01)) == 250


def test_signals_on_crossover():
    close = [100.0] * 60 + [100 + i * 2 for i in range(1, 30)] + [158 - i * 3 for i in range(1, 40)]
    df = pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close, "Volume": 1})
    sig = generate_signals(df, Config(fast_ma=5, slow_ma=20, rsi_overbought=101))["signal"]
    assert (sig == BUY).sum() == 1 and (sig == SELL).sum() == 1
    assert sig[sig == BUY].index[0] < sig[sig == SELL].index[0]


def test_backtest_runs_and_is_consistent():
    res = run_backtest(synthetic(800), Config())
    assert len(res.equity) == 800
    assert res.stats["trades"] == len(res.trades) > 0
    expected = Config().starting_capital + sum(t.pnl for t in res.trades)
    assert abs(res.stats["final_equity"] - expected) < 1e-6 * expected + 1


def test_paper_step_writes_state(tmp_path):
    f = tmp_path / "state.json"
    out = paper_step("X", synthetic(300), Config(), str(f))
    assert f.exists() and "action" in out
