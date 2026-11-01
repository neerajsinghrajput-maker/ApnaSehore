"""Command line se bot chalao.

  python main.py backtest --synthetic                 # bina internet practice
  python main.py backtest --symbol RELIANCE.NS        # real NSE data (yfinance chahiye)
  python main.py backtest --csv data/nifty.csv
  python main.py paper --symbol TCS.NS                # aaj ka paper trade decision
"""
import argparse

from bot.backtest import run_backtest
from bot.config import Config
from bot.data import load_csv, load_yfinance, synthetic
from bot.paper import paper_step


def get_data(args):
    if args.csv:
        return load_csv(args.csv), args.csv
    if args.symbol:
        return load_yfinance(args.symbol, period=args.period), args.symbol
    return synthetic(), "SYNTHETIC"


def main():
    p = argparse.ArgumentParser(description="ApnaSehore Trading Bot")
    p.add_argument("mode", choices=["backtest", "paper"])
    src = p.add_mutually_exclusive_group()
    src.add_argument("--symbol", help="jaise RELIANCE.NS, TCS.NS, BTC-USD")
    src.add_argument("--csv", help="OHLCV CSV file ka path")
    src.add_argument("--synthetic", action="store_true", help="nakli data (default)")
    p.add_argument("--period", default="5y")
    p.add_argument("--fast", type=int, default=20)
    p.add_argument("--slow", type=int, default=50)
    p.add_argument("--capital", type=float, default=100_000)
    p.add_argument("--trades", action="store_true", help="har trade ki list dikhao")
    args = p.parse_args()

    cfg = Config(fast_ma=args.fast, slow_ma=args.slow, starting_capital=args.capital)
    df, name = get_data(args)

    if args.mode == "backtest":
        res = run_backtest(df, cfg)
        print(f"\n=== Backtest: {name} | {df.index[0].date()} -> {df.index[-1].date()} ===")
        for k, v in res.stats.items():
            print(f"  {k:<20} {v}")
        if args.trades:
            print("\n  Entry       Exit        Qty   Entry₹     Exit₹      PnL₹       Reason")
            for t in res.trades:
                print(f"  {t.entry_date.date()}  {t.exit_date.date()}  {t.qty:<5} {t.entry_price:<10.2f} "
                      f"{t.exit_price:<10.2f} {t.pnl:<10.2f} {t.reason}")
    else:
        print(paper_step(name, df, cfg))


if __name__ == "__main__":
    main()
