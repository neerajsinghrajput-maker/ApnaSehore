"""Command line se bot chalao.

Stocks / practice:
  python main.py backtest --synthetic --trades
  python main.py backtest --symbol RELIANCE.NS          # yfinance
  python main.py paper --symbol TCS.NS

Crypto (Delta Exchange / CoinDCX):
  python main.py backtest --exchange delta   --symbol BTCUSD --interval 4h --trades
  python main.py backtest --exchange coindcx --symbol BTCINR --interval 1d
  python main.py scan     --exchange coindcx --symbols BTCINR,ETHINR,SOLINR --interval 1d
  python main.py run      --exchange delta   --symbol BTCUSD --interval 1h --loop      # PAPER
  LIVE_TRADING=YES python main.py run --exchange coindcx --symbol BTCINR --interval 1h \
        --capital 5000 --max-order 2000 --live --loop                                  # LIVE ⚠️
"""
import argparse
import os
import time

from bot.backtest import run_backtest
from bot.config import Config
from bot.data import load_csv, load_yfinance, synthetic
from bot.exchanges import get_exchange
from bot.exchanges.base import ExchangeError, load_dotenv, periods_per_year
from bot.paper import paper_step


def build_exchange(args):
    prefix = "DELTA" if args.exchange.startswith("delta") else args.exchange.upper()
    return get_exchange(args.exchange, api_key=os.getenv(f"{prefix}_API_KEY"),
                        api_secret=os.getenv(f"{prefix}_API_SECRET"))


def build_config(args, ex=None, symbol=None) -> Config:
    cfg = Config(fast_ma=args.fast, slow_ma=args.slow, starting_capital=args.capital,
                 stop_loss_pct=args.sl / 100, take_profit_pct=args.tp / 100,
                 max_order_value=args.max_order)
    if ex is not None:
        cfg.fee_pct = args.fee / 100 if args.fee is not None else ex.default_fee_pct
        cfg.periods_per_year = periods_per_year(args.interval)
        cfg.qty_step = ex.qty_step(symbol)
    elif args.fee is not None:
        cfg.fee_pct = args.fee / 100
    return cfg


def print_backtest(name, df, res, show_trades):
    print(f"\n=== Backtest: {name} | {df.index[0]} -> {df.index[-1]} | {len(df)} candles ===")
    for k, v in res.stats.items():
        print(f"  {k:<20} {v}")
    if show_trades:
        print("\n  Entry                Exit                 Qty        Entry       Exit        PnL        Reason")
        for t in res.trades:
            print(f"  {str(t.entry_date)[:19]:<20} {str(t.exit_date)[:19]:<20} {t.qty:<10g} "
                  f"{t.entry_price:<11.4f} {t.exit_price:<11.4f} {t.pnl:<10.2f} {t.reason}")


def main():
    load_dotenv()
    p = argparse.ArgumentParser(description="ApnaSehore Trading Bot")
    p.add_argument("mode", choices=["backtest", "paper", "scan", "run"])
    p.add_argument("--exchange", help="delta | delta-global | coindcx")
    p.add_argument("--symbol", help="RELIANCE.NS / BTC-USD (yfinance), BTCUSD (Delta), BTCINR (CoinDCX)")
    p.add_argument("--symbols", help="scan ke liye comma list: BTCINR,ETHINR")
    p.add_argument("--csv", help="OHLCV CSV file ka path")
    p.add_argument("--synthetic", action="store_true", help="nakli data")
    p.add_argument("--interval", default="1d", help="1m 5m 15m 30m 1h 2h 4h 6h 1d 1w")
    p.add_argument("--limit", type=int, default=1000, help="kitni candles (backtest)")
    p.add_argument("--period", default="5y", help="yfinance period")
    p.add_argument("--fast", type=int, default=20)
    p.add_argument("--slow", type=int, default=50)
    p.add_argument("--capital", type=float, default=100_000, help="bot ka budget")
    p.add_argument("--sl", type=float, default=5.0, help="stop loss %%")
    p.add_argument("--tp", type=float, default=10.0, help="take profit %%")
    p.add_argument("--fee", type=float, help="fee %% per side (default: exchange ka andaza)")
    p.add_argument("--max-order", type=float, help="ek order ki max value")
    p.add_argument("--trades", action="store_true", help="har trade ki list dikhao")
    p.add_argument("--live", action="store_true", help="⚠️ asli order lagao (run mode)")
    p.add_argument("--loop", action="store_true", help="lagatar chalao (run mode)")
    p.add_argument("--every", type=int, default=60, help="loop mein kitne second baad check")
    p.add_argument("--state", help="state JSON file")
    args = p.parse_args()

    if args.mode in ("scan", "run") and not args.exchange:
        p.error(f"{args.mode} ke liye --exchange chahiye")

    if args.live:
        from bot.runner import live_allowed
        if args.mode != "run":
            p.error("--live sirf run mode ke saath")
        if not live_allowed():
            p.error("LIVE ke liye env LIVE_TRADING=YES set karo (soch samajh kar!)")
        if not args.max_order:
            p.error("LIVE ke liye --max-order zaroori hai (jaise --max-order 2000)")

    if args.exchange:
        ex = build_exchange(args)
        if args.mode == "backtest":
            df = ex.fetch_candles(args.symbol, args.interval, args.limit)
            res = run_backtest(df, build_config(args, ex, args.symbol))
            print_backtest(f"{ex.name} {args.symbol} {args.interval}", df, res, args.trades)
        elif args.mode == "scan":
            print(f"\n{'symbol':<12}{'return%':>9}{'buy&hold%':>11}{'maxDD%':>9}{'sharpe':>8}{'trades':>8}{'win%':>7}")
            for sym in [s.strip() for s in (args.symbols or args.symbol or "").split(",") if s.strip()]:
                try:
                    df = ex.fetch_candles(sym, args.interval, args.limit)
                    s = run_backtest(df, build_config(args, ex, sym)).stats
                    print(f"{sym:<12}{s['total_return_%']:>9}{s['buy_hold_return_%']:>11}{s['max_drawdown_%']:>9}"
                          f"{s['sharpe']:>8}{s['trades']:>8}{s['win_rate_%']:>7}")
                except (ExchangeError, ValueError, OSError) as e:
                    print(f"{sym:<12} error: {e}")
        elif args.mode == "run":
            from bot.runner import run_once
            cfg = build_config(args, ex, args.symbol)
            state = args.state or f"state_{ex.name}_{args.symbol}_{'live' if args.live else 'paper'}.json"
            print(f"{'⚠️  LIVE' if args.live else 'PAPER'} | {ex.name} {args.symbol} {args.interval} | state={state}")
            while True:
                try:
                    print(run_once(ex, args.symbol, args.interval, cfg, state, live=args.live))
                except (ExchangeError, OSError) as e:   # network error par bot band na ho
                    print(f"[error] {e}")
                if not args.loop:
                    break
                time.sleep(args.every)
        else:
            p.error("paper mode yfinance ke liye hai; exchange ke saath 'run' use karo")
        return

    if args.csv:
        df, name = load_csv(args.csv), args.csv
    elif args.symbol:
        df, name = load_yfinance(args.symbol, period=args.period), args.symbol
    else:
        df, name = synthetic(), "SYNTHETIC"
    cfg = build_config(args)
    if args.mode == "backtest":
        print_backtest(name, df, run_backtest(df, cfg), args.trades)
    elif args.mode == "paper":
        print(paper_step(name, df, cfg, args.state or "paper_state.json"))
    else:
        p.error(f"{args.mode} ke liye --exchange chahiye")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot band kiya. 👋")
    except (ExchangeError, OSError) as e:   # network / API error ko saaf message mein dikhao
        raise SystemExit(f"[error] {e}")
