"""Saari settings ek jagah. Yahan values badlo, code nahi."""
from dataclasses import dataclass


@dataclass
class Config:
    # --- Strategy ---
    fast_ma: int = 20          # chhota moving average (din)
    slow_ma: int = 50          # bada moving average (din)
    rsi_period: int = 14
    rsi_overbought: float = 70.0   # isse upar RSI ho to naya BUY mat lo

    # --- Risk management (sabse zaroori) ---
    starting_capital: float = 100_000.0   # ₹1 lakh
    risk_per_trade: float = 0.01          # ek trade mein capital ka max 1% risk
    stop_loss_pct: float = 0.05           # entry se 5% neeche stop loss
    take_profit_pct: float = 0.10         # entry se 10% upar target
    max_position_pct: float = 0.25        # ek stock mein capital ka max 25%

    # --- Costs (India: brokerage + STT + charges ka rough andaza) ---
    fee_pct: float = 0.001                # har buy/sell par 0.1%
    slippage_pct: float = 0.0005          # 0.05% slippage
