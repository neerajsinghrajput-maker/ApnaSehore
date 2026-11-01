"""Technical indicators - sirf pandas se, koi black box nahi."""
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average: pichhle N din ka average."""
    return series.rolling(period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder). 70+ = overbought, 30- = oversold."""
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = gain / loss
    out = 100 - 100 / (1 + rs)
    return out.where(loss != 0, 100.0).where(gain.notna())
