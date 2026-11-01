"""Paper trading: real-time jaisa, lekin nakli paise se. State JSON file mein save hota hai.

Isko roz market close ke baad chalao (ya cron se). Bot latest data dekh kar
decide karega ki BUY / SELL / HOLD, aur paper portfolio update karega.
"""
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from .config import Config
from .risk import position_size, stop_and_target
from .strategy import BUY, SELL, generate_signals


def _load(path: Path, cfg: Config) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {"cash": cfg.starting_capital, "positions": {}, "log": []}


def paper_step(symbol: str, df: pd.DataFrame, cfg: Config, state_file: str = "paper_state.json") -> dict:
    path = Path(state_file)
    state = _load(path, cfg)
    data = generate_signals(df, cfg)
    last = data.iloc[-1]
    price = float(last["Close"])
    cost = cfg.fee_pct + cfg.slippage_pct
    pos = state["positions"].get(symbol)
    action = "HOLD"

    if pos:
        if price <= pos["stop"]:
            action = "SELL (stop loss)"
        elif price >= pos["target"]:
            action = "SELL (target)"
        elif last["signal"] == SELL:
            action = "SELL (signal)"
        if action.startswith("SELL"):
            fill = price * (1 - cost)
            state["cash"] += fill * pos["qty"]
            pnl = (fill - pos["entry"]) * pos["qty"]
            del state["positions"][symbol]
            action += f" qty={pos['qty']} pnl=₹{pnl:,.2f}"
    elif last["signal"] == BUY:
        fill = price * (1 + cost)
        qty = position_size(state["cash"], fill, cfg)
        if qty > 0:
            stop, target = stop_and_target(fill, cfg)
            state["cash"] -= fill * qty
            state["positions"][symbol] = {"qty": qty, "entry": fill, "stop": stop, "target": target}
            action = f"BUY qty={qty} @ ₹{fill:,.2f} SL=₹{stop:,.2f} TGT=₹{target:,.2f}"

    entry = {"time": datetime.now().isoformat(timespec="seconds"), "symbol": symbol,
             "price": round(price, 2), "rsi": round(float(last["rsi"]), 1), "action": action}
    state["log"].append(entry)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    return entry
