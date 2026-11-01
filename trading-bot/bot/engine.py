"""Trading engine: paper aur live dono ek hi logic use karte hain.

decide() sirf faisla karta hai (BUY / SELL / HOLD), apply() portfolio update karta hai.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from .config import Config
from .risk import position_size, stop_and_target
from .strategy import BUY, SELL


def new_state(cfg: Config) -> dict:
    return {"cash": cfg.starting_capital, "positions": {}, "log": [],
            "day": "", "day_start_equity": cfg.starting_capital, "last_candle": {}}


def load_state(path: str | Path, cfg: Config) -> dict:
    p = Path(path)
    state = json.loads(p.read_text()) if p.exists() else new_state(cfg)
    for k, v in new_state(cfg).items():
        state.setdefault(k, v)
    return state


def save_state(path: str | Path, state: dict) -> None:
    state["log"] = state["log"][-500:]
    Path(path).write_text(json.dumps(state, indent=2, ensure_ascii=False))


def equity(state: dict, prices: dict[str, float]) -> float:
    return state["cash"] + sum(p["qty"] * prices.get(s, p["entry"]) for s, p in state["positions"].items())


def decide(state: dict, symbol: str, signal: int, price: float, cfg: Config) -> dict:
    cost = cfg.fee_pct + cfg.slippage_pct
    pos = state["positions"].get(symbol)
    if pos:
        if price <= pos["stop"]:
            return {"action": "SELL", "qty": pos["qty"], "reason": "stop_loss"}
        if price >= pos["target"]:
            return {"action": "SELL", "qty": pos["qty"], "reason": "take_profit"}
        if signal == SELL:
            return {"action": "SELL", "qty": pos["qty"], "reason": "signal"}
        return {"action": "HOLD", "reason": "in_position"}
    if signal == BUY:
        qty = position_size(state["cash"], price * (1 + cost), cfg)
        if qty > 0:
            return {"action": "BUY", "qty": qty, "reason": "signal"}
        return {"action": "HOLD", "reason": "qty_zero (budget kam hai)"}
    return {"action": "HOLD", "reason": "no_signal"}


def apply(state: dict, symbol: str, d: dict, price: float, cfg: Config) -> dict:
    """Fill ko portfolio mein likho. Return: log entry."""
    cost = cfg.fee_pct + cfg.slippage_pct
    entry = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "symbol": symbol,
             "price": round(price, 6), **d}
    if d["action"] == "BUY":
        fill = price * (1 + cost)
        stop, target = stop_and_target(fill, cfg)
        state["cash"] -= fill * d["qty"]
        state["positions"][symbol] = {"qty": d["qty"], "entry": fill, "stop": stop, "target": target}
        entry.update(fill=round(fill, 6), stop=round(stop, 6), target=round(target, 6))
    elif d["action"] == "SELL":
        pos = state["positions"].pop(symbol)
        fill = price * (1 - cost)
        state["cash"] += fill * pos["qty"]
        entry.update(fill=round(fill, 6), pnl=round((fill - pos["entry"]) * pos["qty"], 2))
    state["log"].append(entry)
    return entry
