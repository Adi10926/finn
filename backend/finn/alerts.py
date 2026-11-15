"""Triggered alerts. The investor defines 'unusual'; FINN watches.

Rules (all thresholds user-set):
  volume  : today's volume >= k x average of previous N sessions
  price   : |day move| >= x %
  filing  : a filing in a category the user cares about, scored 'act'
"""
from __future__ import annotations


def eod_alerts(series: list[dict], vol_mult: float, lookback: int, move_pct: float, days: int = 5) -> list[dict]:
    out = []
    for t in range(max(lookback + 1, len(series) - days), len(series)):
        today, prev = series[t], series[t - 1]
        window = series[t - lookback:t]
        avg = sum(d["volume"] for d in window) / len(window)
        vm = today["volume"] / avg if avg else 0
        mv = (today["close"] / prev["close"] - 1) * 100
        hit = []
        if vm >= vol_mult:
            hit.append({"rule": "volume", "text": f"Volume {vm:.1f}× its {lookback}-day average", "value": round(vm, 2)})
        if abs(mv) >= move_pct:
            hit.append({"rule": "price", "text": f"{'Up' if mv > 0 else 'Down'} {abs(mv):.1f}% on the day", "value": round(mv, 2)})
        if hit:
            out.append({"date": today["date"], "close": today["close"], "move_pct": round(mv, 2),
                        "vol_mult": round(vm, 2), "hits": hit})
    return out
