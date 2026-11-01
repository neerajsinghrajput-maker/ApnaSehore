"""Backtest: purane data par strategy chala kar dekho ki kya hota.

Look-ahead bias se bachne ke liye: aaj ke close par signal banta hai,
order AGLE din ke Open par fill hota hai.
"""
from dataclasses import dataclass, field

import pandas as pd

from .config import Config
from .risk import position_size, stop_and_target
from .strategy import BUY, SELL, generate_signals


@dataclass
class Trade:
    entry_date: pd.Timestamp
    entry_price: float
    qty: int
    exit_date: pd.Timestamp | None = None
    exit_price: float | None = None
    reason: str = ""

    @property
    def pnl(self) -> float:
        return 0.0 if self.exit_price is None else (self.exit_price - self.entry_price) * self.qty


@dataclass
class Result:
    trades: list[Trade] = field(default_factory=list)
    equity: pd.Series | None = None
    stats: dict = field(default_factory=dict)


def run_backtest(df: pd.DataFrame, cfg: Config) -> Result:
    data = generate_signals(df, cfg)
    cash = cfg.starting_capital
    trade: Trade | None = None
    stop = target = 0.0
    trades: list[Trade] = []
    equity = []
    cost = cfg.fee_pct + cfg.slippage_pct

    rows = list(data.itertuples())
    for i, row in enumerate(rows):
        # 1) Open position: pehle stop loss / target check karo (intraday High/Low se)
        if trade is not None:
            exit_px = reason = None
            if row.Low <= stop:
                exit_px, reason = min(stop, row.Open), "stop_loss"  # gap-down ho to open par
            elif row.High >= target:
                exit_px, reason = max(target, row.Open), "take_profit"
            if exit_px is not None:
                fill = exit_px * (1 - cost)
                cash += fill * trade.qty
                trade.exit_date, trade.exit_price, trade.reason = row.Index, fill, reason
                trades.append(trade)
                trade = None

        # 2) Kal ke signal ko aaj ke Open par execute karo
        if i > 0:
            sig = rows[i - 1].signal
            if sig == BUY and trade is None:
                fill = row.Open * (1 + cost)
                qty = position_size(cash, fill, cfg)
                if qty > 0:
                    cash -= fill * qty
                    trade = Trade(row.Index, fill, qty)
                    stop, target = stop_and_target(fill, cfg)
            elif sig == SELL and trade is not None:
                fill = row.Open * (1 - cost)
                cash += fill * trade.qty
                trade.exit_date, trade.exit_price, trade.reason = row.Index, fill, "signal"
                trades.append(trade)
                trade = None

        equity.append(cash + (trade.qty * row.Close if trade else 0.0))

    if trade is not None:  # end mein khuli position band karo
        last = rows[-1]
        fill = last.Close * (1 - cost)
        cash += fill * trade.qty
        trade.exit_date, trade.exit_price, trade.reason = last.Index, fill, "end_of_data"
        trades.append(trade)
        equity[-1] = cash

    eq = pd.Series(equity, index=data.index, name="equity")
    return Result(trades, eq, compute_stats(eq, trades, data["Close"], cfg))


def compute_stats(eq: pd.Series, trades: list[Trade], close: pd.Series, cfg: Config) -> dict:
    daily = eq.pct_change().dropna()
    years = max(len(eq) / cfg.periods_per_year, 1e-9)
    final = eq.iloc[-1]
    wins = [t for t in trades if t.pnl > 0]
    sharpe = (daily.mean() / daily.std() * cfg.periods_per_year**0.5) if daily.std() > 0 else 0.0
    gross_win = sum(t.pnl for t in wins)
    gross_loss = -sum(t.pnl for t in trades if t.pnl <= 0)
    return {
        "start_capital": cfg.starting_capital,
        "final_equity": round(final, 2),
        "total_return_%": round((final / cfg.starting_capital - 1) * 100, 2),
        "buy_hold_return_%": round((close.iloc[-1] / close.iloc[0] - 1) * 100, 2),
        "CAGR_%": round(((final / cfg.starting_capital) ** (1 / years) - 1) * 100, 2),
        "max_drawdown_%": round(((eq / eq.cummax()) - 1).min() * 100, 2),
        "sharpe": round(sharpe, 2),
        "trades": len(trades),
        "win_rate_%": round(len(wins) / len(trades) * 100, 1) if trades else 0.0,
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else float("inf"),
    }
