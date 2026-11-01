"""Sab exchanges ke liye common interface."""
import os
from abc import ABC, abstractmethod

import pandas as pd
import requests

# candle interval -> (pandas timedelta, saal mein kitni candles)
INTERVALS = {
    "1m": ("1min", 525_600), "5m": ("5min", 105_120), "15m": ("15min", 35_040),
    "30m": ("30min", 17_520), "1h": ("1h", 8_760), "2h": ("2h", 4_380),
    "4h": ("4h", 2_190), "6h": ("6h", 1_460), "1d": ("1D", 365), "1w": ("7D", 52),
}


def interval_timedelta(interval: str) -> pd.Timedelta:
    if interval not in INTERVALS:
        raise ValueError(f"Interval {interval} support nahi hai. Options: {list(INTERVALS)}")
    return pd.Timedelta(INTERVALS[interval][0])


def periods_per_year(interval: str) -> int:
    return INTERVALS[interval][1]


def load_dotenv(path: str = ".env") -> None:
    """Simple .env loader (KEY=VALUE lines). Keys kabhi code ya GitHub mein mat daalo."""
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class ExchangeError(RuntimeError):
    pass


class Exchange(ABC):
    name = "base"
    quote_asset = "USD"      # balance kis currency mein dekhna hai
    default_fee_pct = 0.001

    def __init__(self, api_key: str | None = None, api_secret: str | None = None,
                 session: requests.Session | None = None, timeout: float = 15):
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = session or requests.Session()
        self.timeout = timeout

    @property
    def has_keys(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def _require_keys(self):
        if not self.has_keys:
            raise ExchangeError(f"{self.name}: API key/secret nahi mile. .env file check karo.")

    @staticmethod
    def _check(resp: requests.Response):
        try:
            data = resp.json()
        except ValueError:
            raise ExchangeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        if resp.status_code >= 400 or (isinstance(data, dict) and data.get("success") is False):
            raise ExchangeError(f"HTTP {resp.status_code}: {str(data)[:300]}")
        return data

    # ---- public ----
    @abstractmethod
    def fetch_candles(self, symbol: str, interval: str = "1d", limit: int = 500) -> pd.DataFrame:
        """OHLCV DataFrame (UTC index, purani -> nayi)."""

    @abstractmethod
    def qty_step(self, symbol: str) -> float:
        """Base asset (jaise BTC) ki minimum quantity step."""

    # ---- private (keys chahiye) ----
    @abstractmethod
    def get_balance(self, asset: str | None = None) -> float:
        """Available balance (default: quote_asset)."""

    @abstractmethod
    def place_market_order(self, symbol: str, side: str, qty: float) -> dict:
        """side = 'buy' / 'sell'. qty base asset mein (jaise 0.01 BTC)."""


def to_frame(rows: list[dict], time_key: str, unit: str) -> pd.DataFrame:
    if not rows:
        raise ExchangeError("Exchange ne koi candle nahi di. Symbol / interval check karo.")
    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(df[time_key].astype("int64"), unit=unit, utc=True)
    df = df.rename(columns=str.capitalize)[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    return df[~df.index.duplicated(keep="last")].sort_index()
