"""Market data lana: CSV file, yfinance, ya offline practice ke liye synthetic data."""
from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED = ["Open", "High", "Low", "Close", "Volume"]


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):  # yfinance kabhi-kabhi multi-level deta hai
        df.columns = df.columns.get_level_values(0)
    df.columns = [str(c).strip().capitalize() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Data mein ye columns nahi mile: {missing}")
    return df[REQUIRED].dropna().sort_index()


def load_csv(path: str | Path) -> pd.DataFrame:
    """CSV jisme Date, Open, High, Low, Close, Volume columns hon."""
    df = pd.read_csv(path, parse_dates=[0], index_col=0)
    return _clean(df)


def load_yfinance(symbol: str, period: str = "5y", interval: str = "1d") -> pd.DataFrame:
    """Real data. NSE ke liye '.NS' lagao (RELIANCE.NS), crypto: BTC-USD."""
    try:
        import yfinance as yf
    except ImportError as e:
        raise SystemExit("yfinance install karo: pip install yfinance") from e
    df = yf.download(symbol, period=period, interval=interval, auto_adjust=True, progress=False)
    if df.empty:
        raise SystemExit(f"{symbol} ka data nahi mila. Symbol check karo.")
    return _clean(df)


def synthetic(days: int = 1000, seed: int = 42, start_price: float = 1000.0) -> pd.DataFrame:
    """Nakli (random walk) data, bina internet ke practice ke liye."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.0004, 0.018, days)
    # thode trends daalo taaki strategy ke paas kuch karne ko ho
    returns += 0.002 * np.sin(np.linspace(0, 12 * np.pi, days))
    close = start_price * np.exp(np.cumsum(returns))
    open_ = np.concatenate([[start_price], close[:-1]])
    spread = np.abs(rng.normal(0, 0.008, days)) * close
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    volume = rng.integers(100_000, 1_000_000, days)
    idx = pd.bdate_range("2020-01-01", periods=days)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume}, index=idx
    )
