"""Exchange adapters. Naya exchange jodna ho to base.Exchange ko implement karo."""
from .base import Exchange
from .coindcx import CoinDCX
from .delta import DeltaExchange


def get_exchange(name: str, **kwargs) -> Exchange:
    name = name.lower()
    if name in ("delta", "delta-india", "delta_india"):
        return DeltaExchange(region="india", **kwargs)
    if name in ("delta-global", "delta_global"):
        return DeltaExchange(region="global", **kwargs)
    if name == "coindcx":
        return CoinDCX(**kwargs)
    raise ValueError(f"Unknown exchange: {name}. Options: delta, delta-global, coindcx")
