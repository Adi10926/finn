"""End-of-day price & volume.

Live: yfinance (SYMBOL.NS, falls back to .BO). Cached for 6h.
Offline (no network, e.g. CI or this repo's sandbox): a seeded random walk anchored to the
snapshot close, clearly flagged `simulated=True` all the way to the UI. Never mixed silently.
"""
from __future__ import annotations

import datetime as dt
import math
import random

from .. import store
from ..config import LIVE


def _trading_days(end: dt.date, n: int) -> list[dt.date]:
    out, d = [], end
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= dt.timedelta(days=1)
    return out[::-1]


def _yahoo(symbol: str, days: int = 90):
    import yfinance as yf  # imported lazily: heavy

    for suffix in (".NS", ".BO"):
        try:
            df = yf.Ticker(symbol + suffix).history(period=f"{days}d", interval="1d", auto_adjust=False)
        except Exception:
            df = None
        if df is not None and len(df) > 5:
            return [{"date": i.strftime("%Y-%m-%d"), "close": round(float(r.Close), 2),
                     "volume": int(r.Volume)} for i, r in df.iterrows()]
    return None


def _simulated(symbol: str, last_close: float, end: dt.date, n: int = 60):
    rng = random.Random(symbol)  # deterministic per ticker
    days = _trading_days(end, n)
    vol = 0.012 + rng.random() * 0.012
    base_vol = 10 ** (5 + rng.random() * 2)
    closes, p = [], 1.0
    for _ in days:
        p *= math.exp(rng.gauss(0, vol))
        closes.append(p)
    scale = last_close / closes[-1]
    series = []
    for d, c in zip(days, closes):
        v = base_vol * math.exp(rng.gauss(0, 0.35))
        series.append({"date": d.isoformat(), "close": round(c * scale, 2), "volume": int(v)})
    return series


def eod(symbol: str, last_close: float | None, as_of: dt.date) -> dict:
    k = store.key("eod", symbol, as_of.isoformat())
    hit = store.get(k, ttl=6 * 3600)
    if hit:
        return hit
    series = _yahoo(symbol) if LIVE else None
    out = {"symbol": symbol, "series": series or [], "simulated": False, "source": "yahoo"}
    if not series:
        out.update(series=_simulated(symbol, last_close or 100.0, as_of), simulated=True,
                   source="simulated (no market-data access)")
    else:
        store.put(k, out)
    return out
