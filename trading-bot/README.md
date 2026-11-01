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
| `bot/exchanges/` | Delta Exchange + CoinDCX adapters (candles, balance, order) |
| `bot/engine.py` | BUY/SELL/HOLD faisla + portfolio update (paper & live same logic) |
| `bot/runner.py` | Exchange par paper/live loop + safety checks |
| `bot/notify.py` | Telegram alerts |
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

## 🪙 Crypto: Delta Exchange & CoinDCX

| | **Delta Exchange (India)** | **CoinDCX** |
|---|---|---|
| Type | Futures / perpetual (BTCUSD, ETHUSD…) | Spot (BTCINR, ETHINR, BTCUSDT…) |
| Quantity | Contracts (BTCUSD: 1 contract = 0.001 BTC) | Coin mein (0.0012 BTC) |
| Balance | USD | INR (ya USDT) |
| `--exchange` | `delta` (global ke liye `delta-global`) | `coindcx` |
| Keys `.env` mein | `DELTA_API_KEY`, `DELTA_API_SECRET` | `COINDCX_API_KEY`, `COINDCX_API_SECRET` |

Ye bot sirf **LONG** jaata hai (pehle buy, phir sell). Delta par sell order `reduce_only` hota hai,
taaki galti se short position na khule. Bot leverage set nahi karta, lekin Delta par margin
product ki leverage setting se lagta hai. Isliye `--capital` aur `--max-order` chhote rakho.

### Crypto commands

```bash
cp .env.example .env            # keys sirf live ke liye chahiye; backtest/paper bina keys chalega

# Backtest (exchange ka asli data, keys nahi chahiye)
python main.py backtest --exchange delta   --symbol BTCUSD --interval 4h --trades
python main.py backtest --exchange coindcx --symbol BTCINR --interval 1d --limit 1000

# Kai coins ek saath compare karo
python main.py scan --exchange coindcx --symbols BTCINR,ETHINR,SOLINR,XRPINR --interval 1d
python main.py scan --exchange delta   --symbols BTCUSD,ETHUSD,SOLUSD --interval 4h

# PAPER trading: asli live price, nakli paisa. Har 60 sec check karta hai (Ctrl+C se band)
python main.py run --exchange delta --symbol BTCUSD --interval 1h --capital 100 --loop

# LIVE ⚠️ (paper mein 1-3 mahine theek chalne ke BAAD hi)
LIVE_TRADING=YES python main.py run --exchange coindcx --symbol BTCINR --interval 1h \
    --capital 5000 --max-order 2000 --live --loop
```

Useful options: `--fast 10 --slow 30`, `--sl 3 --tp 6` (percent), `--fee 0.1` (percent per side).

### Live safety (bot mein built-in)

- **3 taale:** `--live` flag, `LIVE_TRADING=YES` env aur `--max-order`, teeno chahiye. Ek bhi na ho to order nahi lagega.
- **Kill switch:** bot folder mein `STOP` naam ki file bana do (`touch STOP`). Bot koi trade nahi karega.
- **Daily loss limit:** din mein 3% loss ho jaaye to naye BUY band.
- **Sirf closed candle par signal**, aur ek candle ka signal ek hi baar use hota hai.
- **Order se pehle balance check.** Error aaye to state update nahi hoti aur Telegram alert jaata hai.
- **Stop loss bot khud check karta hai** (har `--every` second). Isliye bot 24x7 chalna chahiye (VPS).
  Bot band hua to SL nahi lagega. Exchange par manual stop order bhi rakhna safe hai.

### API key banane ke rules

1. Sirf **Trading** permission do. **Withdrawal kabhi nahi.**
2. **IP whitelist** lagao (apne VPS ka IP).
3. Keys sirf `.env` mein rakho. `.env` `.gitignore` mein hai, GitHub par nahi jaayegi.

### India tax note

Crypto (VDA) ke profit par 30% tax lagta hai aur losses set-off nahi hote. Indian exchanges par
sell karne par 1% TDS katta hai. Bot ke paper/backtest numbers mein ye tax shamil **nahi** hai.
Bahut zyada trades = bahut zyada TDS, isliye CA se zaroor baat karo.

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
- [x] **Step 4 – Crypto + scan:** Delta Exchange & CoinDCX adapters, kai coins ek saath scan
- [ ] **Step 5 – Strategy improve:** parameters test karo (sirf purane data par fit mat karo – *overfitting* se bacho; data ko train/test mein baanto)
- [x] **Step 6 – Alerts:** Telegram par BUY/SELL message (`.env` mein token)
- [x] **Step 7 – Exchange API:** Delta / CoinDCX par order (chhoti qty se shuru karo!)
- [x] **Step 8 – Live safety:** max order cap, daily loss limit, kill switch, keys `.env` mein
- [ ] **Step 9 – Deploy:** VPS / cloud par schedule (cron) ke saath

## Golden rules

1. Ek trade mein capital ka **1–2% se zyada risk** nahi (ye bot default 1% rakhta hai).
2. **Stop loss hamesha.**
3. Backtest achha dikhe to bhi shak karo – asli market mein slippage, gap, aur emotions hote hain.
4. SEBI rules: algo trading broker ke approved API se hi karo.
