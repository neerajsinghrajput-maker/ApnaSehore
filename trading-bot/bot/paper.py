"""Paper trading (daily data, jaise yfinance): roz ek baar chalao. State JSON mein save hota hai."""
import pandas as pd

from .config import Config
from .engine import apply, decide, load_state, save_state
from .strategy import generate_signals


def paper_step(symbol: str, df: pd.DataFrame, cfg: Config, state_file: str = "paper_state.json") -> dict:
    state = load_state(state_file, cfg)
    last = generate_signals(df, cfg).iloc[-1]
    price = float(last["Close"])
    entry = apply(state, symbol, decide(state, symbol, int(last["signal"]), price, cfg), price, cfg)
    entry["rsi"] = round(float(last["rsi"]), 1)
    save_state(state_file, state)
    return entry
