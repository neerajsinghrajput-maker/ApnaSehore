"""Risk management - bot ko zinda rakhne wala hissa."""
import math

from .config import Config


def position_size(capital: float, price: float, cfg: Config) -> int:
    """Kitne shares lene hain, taaki stop loss lage to sirf risk_per_trade jitna nuksaan ho."""
    if price <= 0:
        return 0
    risk_amount = capital * cfg.risk_per_trade
    loss_per_share = price * cfg.stop_loss_pct
    qty_by_risk = risk_amount / loss_per_share
    qty_by_cap = (capital * cfg.max_position_pct) / price
    return max(0, math.floor(min(qty_by_risk, qty_by_cap)))


def stop_and_target(entry: float, cfg: Config) -> tuple[float, float]:
    return entry * (1 - cfg.stop_loss_pct), entry * (1 + cfg.take_profit_pct)
