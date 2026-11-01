"""Exchange se live data le kar bot chalana - PAPER (default) ya LIVE.

Safety:
  * LIVE tabhi jab --live flag + env LIVE_TRADING=YES + --max-order set ho
  * Folder mein 'STOP' naam ki file bana do -> bot koi trade nahi karega (kill switch)
  * Din ka loss max_daily_loss_pct se zyada -> naye BUY band
  * Sirf BAND (closed) candle par signal; ek candle ka signal ek hi baar use hota hai
"""
import os
from pathlib import Path

import pandas as pd

from .config import Config
from .engine import apply, decide, equity, load_state, save_state
from .exchanges.base import Exchange, ExchangeError, interval_timedelta
from .notify import notify
from .strategy import HOLD, generate_signals

KILL_SWITCH = "STOP"


def live_allowed() -> bool:
    return os.getenv("LIVE_TRADING", "").upper() == "YES"


def run_once(ex: Exchange, symbol: str, interval: str, cfg: Config, state_file: str,
             live: bool = False, now: pd.Timestamp | None = None) -> dict:
    mode = "LIVE" if live else "PAPER"
    if live and not live_allowed():
        raise SystemExit("LIVE ke liye env LIVE_TRADING=YES set karo (soch samajh kar!).")
    if live and not cfg.max_order_value:
        raise SystemExit("LIVE ke liye --max-order zaroori hai (jaise --max-order 2000).")

    state = load_state(state_file, cfg)
    now = now or pd.Timestamp.now(tz="UTC")
    raw = ex.fetch_candles(symbol, interval, limit=max(cfg.slow_ma * 3, 300))
    closed = raw[raw.index + interval_timedelta(interval) <= now]
    if len(closed) < cfg.slow_ma + 2:
        raise ExchangeError(f"Kam candles mili ({len(closed)}). Interval/symbol check karo.")

    price = float(raw["Close"].iloc[-1])        # abhi ka price (chalti candle)
    data = generate_signals(closed, cfg)
    candle_t = str(closed.index[-1])
    signal = int(data["signal"].iloc[-1])
    if state["last_candle"].get(symbol) == candle_t:
        signal = HOLD                            # is candle ka signal pehle hi dekh liya

    # daily loss limit
    today = str(now.date())
    eq = equity(state, {symbol: price})
    if state["day"] != today:
        state["day"], state["day_start_equity"] = today, eq

    d = decide(state, symbol, signal, price, cfg)

    if Path(KILL_SWITCH).exists():
        d = {"action": "HOLD", "reason": "KILL SWITCH (STOP file) on"}
    elif d["action"] == "BUY" and eq < state["day_start_equity"] * (1 - cfg.max_daily_loss_pct):
        d = {"action": "HOLD", "reason": "daily loss limit hit"}

    if d["action"] != "HOLD" and live:
        try:
            if d["action"] == "BUY":
                need = d["qty"] * price * (1 + cfg.fee_pct)
                bal = ex.get_balance()
                if bal < need:
                    raise ExchangeError(f"Balance kam: {bal:.2f} {ex.quote_asset}, chahiye {need:.2f}")
            order = ex.place_market_order(symbol, d["action"].lower(), d["qty"])
            d["order_id"] = (order or {}).get("id") if isinstance(order, dict) else None
        except ExchangeError as e:
            notify(f"❌ [{mode}] {ex.name} {symbol} {d['action']} fail: {e}")
            save_state(state_file, state)
            return {"action": "ERROR", "error": str(e)}

    entry = apply(state, symbol, d, price, cfg)
    entry.update(mode=mode, candle=candle_t, rsi=round(float(data["rsi"].iloc[-1]), 1),
                 equity=round(equity(state, {symbol: price}), 2))
    state["last_candle"][symbol] = candle_t
    save_state(state_file, state)

    if d["action"] != "HOLD":
        extra = f" pnl={entry['pnl']}" if "pnl" in entry else f" SL={entry['stop']} TGT={entry['target']}"
        notify(f"🤖 [{mode}] {ex.name} {symbol} {d['action']} qty={d['qty']} @ {price}{extra} ({d['reason']})")
    return entry
