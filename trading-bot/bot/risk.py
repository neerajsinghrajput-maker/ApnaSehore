"""Risk management - bot ko zinda rakhne wala hissa."""
import math

from .config import Config


def round_step(qty: float, step: float) -> float:
    """Quantity ko step ke multiple tak neeche round karo (0.12345 BTC, step 0.001 -> 0.123)."""
    if step <= 0:
        return qty
    n = math.floor(qty / step + 1e-9)
    decimals = max(0, -int(math.floor(math.log10(step)))) if step < 1 else 0
    return round(n * step, decimals) if step < 1 else n * step


def position_size(capital: float, price: float, cfg: Config) -> float:
    """Kitni quantity leni hai, taaki stop loss lage to sirf risk_per_trade jitna nuksaan ho."""
    if price <= 0 or capital <= 0:
        return 0
    risk_amount = capital * cfg.risk_per_trade
    loss_per_unit = price * cfg.stop_loss_pct
    qty_by_risk = risk_amount / loss_per_unit
    qty_by_cap = (capital * cfg.max_position_pct) / price
    qty = min(qty_by_risk, qty_by_cap)
    if cfg.max_order_value:
        qty = min(qty, cfg.max_order_value / price)
    out = round_step(qty, cfg.qty_step)
    return int(out) if cfg.qty_step >= 1 else out


def stop_and_target(entry: float, cfg: Config) -> tuple[float, float]:
    return entry * (1 - cfg.stop_loss_pct), entry * (1 + cfg.take_profit_pct)
