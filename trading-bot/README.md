# 🤖 ApnaSehore Trading Bot — Zero se Live tak

> ⚠️ **Zaroori chetavni:** Trading mein paisa doob sakta hai. Ye bot seekhne ke liye hai.
> Real paisa tab tak mat lagao jab tak backtest + kam se kam 1–3 mahine paper trading
> mein strategy theek na chale. Ye financial advice nahi hai.

## Bot kaise kaam karta hai (4 hisse)

```
Data  ──►  Strategy  ──►  Risk Management  ──►  Execution
(OHLCV)    (BUY/SELL)     (kitna, SL, target)    (backtest / paper / live)
```

| File | Kaam |
|------|------|
| `bot/config.py` | Saari settings (MA period, risk %, stop loss, fees) |
| `bot/data.py` | Data lana: CSV, yfinance (NSE / crypto), ya synthetic |
| `bot/indicators.py` | SMA, RSI |
| `bot/strategy.py` | MA crossover + RSI filter → BUY / SELL signal |
| `bot/risk.py` | Position size (1% risk rule), stop loss, target |
| `bot/backtest.py` | Purane data par test + stats (return, drawdown, Sharpe, win rate) |
| `bot/paper.py` | Nakli paise se roz ka trading decision, `paper_state.json` mein save |
| `main.py` | Command line |

## Setup

```bash
cd trading-bot
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -q tests        # sab test pass hone chahiye
```

## Chalao

```bash
# 1. Bina internet practice (nakli data)
python main.py backtest --synthetic --trades

# 2. Real NSE stock (5 saal ka data)
python main.py backtest --symbol RELIANCE.NS --trades
python main.py backtest --symbol TCS.NS --fast 10 --slow 30

# 3. Crypto
python main.py backtest --symbol BTC-USD

# 4. Paper trading – roz market close (3:30 PM) ke baad ek baar chalao
python main.py paper --symbol INFY.NS
```

## Stats ka matlab

- **total_return_% vs buy_hold_return_%** – bot ne simply "khareed ke rakh lo" se behtar kiya ya nahi?
- **max_drawdown_%** – peak se sabse bada girav. -20% se zyada = dard bhara.
- **sharpe** – risk ke hisaab se return. 1+ achha, 0.5 se kam kamzor.
- **win_rate_%** – kitne trade profit mein. 40% bhi theek hai agar profit_factor > 1.5 ho.
- **profit_factor** – kul profit ÷ kul loss. 1 se kam = strategy paisa kha rahi hai.

## 🗺️ Roadmap: Zero → Live

- [x] **Step 1 – Basics:** data, indicators, strategy, risk management
- [x] **Step 2 – Backtest:** fees + slippage ke saath, look-ahead bias ke bina
- [x] **Step 3 – Paper trading:** roz ka decision, portfolio JSON mein
- [ ] **Step 4 – Multiple stocks:** NIFTY 50 list par ek saath scan
- [ ] **Step 5 – Strategy improve:** parameters test karo (sirf purane data par fit mat karo – *overfitting* se bacho; data ko train/test mein baanto)
- [ ] **Step 6 – Alerts:** Telegram par BUY/SELL message
- [ ] **Step 7 – Broker API:** Zerodha Kite Connect / Angel One SmartAPI / Upstox (crypto: Binance/CoinDCX) – pehle unke **sandbox/chhote qty** se
- [ ] **Step 8 – Live safety:** max daily loss limit, kill switch, logging, API keys `.env` mein (kabhi GitHub par push mat karo)
- [ ] **Step 9 – Deploy:** VPS / cloud par schedule (cron) ke saath

## Golden rules

1. Ek trade mein capital ka **1–2% se zyada risk** nahi (ye bot default 1% rakhta hai).
2. **Stop loss hamesha.**
3. Backtest achha dikhe to bhi shak karo – asli market mein slippage, gap, aur emotions hote hain.
4. SEBI rules: algo trading broker ke approved API se hi karo.
