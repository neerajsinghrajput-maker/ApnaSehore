"""Saari settings ek jagah. Yahan values badlo, code nahi."""
from dataclasses import dataclass


@dataclass
class Config:
    # --- Strategy ---
    fast_ma: int = 20          # chhota moving average (candles)
    slow_ma: int = 50          # bada moving average (candles)
    rsi_period: int = 14
    rsi_overbought: float = 70.0   # isse upar RSI ho to naya BUY mat lo

    # --- Risk management (sabse zaroori) ---
    starting_capital: float = 100_000.0   # bot ka budget (INR / USD / USDT)
    risk_per_trade: float = 0.01          # ek trade mein capital ka max 1% risk
    stop_loss_pct: float = 0.05           # entry se 5% neeche stop loss
    take_profit_pct: float = 0.10         # entry se 10% upar target
    max_position_pct: float = 0.25        # ek coin/stock mein capital ka max 25%
    qty_step: float = 1.0                 # quantity kitne step mein (stocks 1, BTC 0.0001)

    # --- Costs ---
    fee_pct: float = 0.001                # har buy/sell par
    slippage_pct: float = 0.0005

    # --- Stats ---
    periods_per_year: int = 252           # stocks 252 din; crypto 1d = 365, 1h = 8760

    # --- Live safety ---
    max_order_value: float | None = None  # ek order ki max value (live mein zaroor set karo)
    max_daily_loss_pct: float = 0.03      # din mein 3% loss -> naye BUY band
