"""Strategy: kab BUY karna hai, kab SELL.

Moving Average Crossover + RSI filter:
  BUY  -> fast MA, slow MA ko neeche se upar cross kare AUR RSI overbought na ho
  SELL -> fast MA, slow MA ko upar se neeche cross kare
(Stop loss / target risk.py + backtest mein handle hote hain.)
"""
import pandas as pd

from .config import Config
from .indicators import rsi, sma

BUY, SELL, HOLD = 1, -1, 0


def generate_signals(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    out = df.copy()
    out["fast"] = sma(out["Close"], cfg.fast_ma)
    out["slow"] = sma(out["Close"], cfg.slow_ma)
    out["rsi"] = rsi(out["Close"], cfg.rsi_period)

    above = out["fast"] > out["slow"]
    prev_above = above.shift(1, fill_value=False)
    valid = out["slow"].notna() & out["slow"].shift(1).notna()
    cross_up = above & ~prev_above & valid
    cross_down = ~above & prev_above & valid

    out["signal"] = HOLD
    out.loc[cross_up & (out["rsi"] < cfg.rsi_overbought), "signal"] = BUY
    out.loc[cross_down, "signal"] = SELL
    return out
