"""Corporate announcements from NSE (primary) and BSE (fallback), else the Screener snapshot.

NSE's JSON API needs a cookie from the homepage first; BSE's needs a Referer. Both are
public, end-of-day friendly, and cached for 30 minutes.
"""
from __future__ import annotations

import datetime as dt

import httpx

from .. import store
from ..config import LIVE, USER_AGENT
from ..seed import load

NSE_HOME = "https://www.nseindia.com"
NSE_API = ("https://www.nseindia.com/api/corporate-announcements?index=equities&symbol={s}"
           "&from_date={f}&to_date={t}")


def _nse(symbol: str, start: dt.date, end: dt.date):
    h = {"User-Agent": USER_AGENT, "Accept": "application/json", "Referer": NSE_HOME}
    with httpx.Client(headers=h, timeout=20, follow_redirects=True) as c:
        c.get(NSE_HOME)  # sets nsit / nseappid cookies
        r = c.get(NSE_API.format(s=symbol, f=start.strftime("%d-%m-%Y"), t=end.strftime("%d-%m-%Y")))
        r.raise_for_status()
        rows = r.json()
    out = []
    for a in rows if isinstance(rows, list) else rows.get("data", []):
        when = a.get("sort_date") or a.get("an_dt") or ""
        try:
            d = dt.datetime.strptime(when[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                d = dt.datetime.strptime(when[:20], "%d-%b-%Y %H:%M:%S")
            except ValueError:
                continue
        out.append({"date": d.strftime("%Y-%m-%d"), "time": d.strftime("%H:%M"),
                    "title": a.get("desc", ""), "desc": (a.get("attchmntText") or "")[:400],
                    "url": a.get("attchmntFile", ""), "source": "NSE"})
    return out


def fetch(symbol: str, start: dt.date, end: dt.date) -> tuple[list[dict], str]:
    """Return (announcements, source_label)."""
    k = store.key("ann", symbol, start, end)
    hit = store.get(k, ttl=1800)
    if hit:
        return hit["rows"], hit["src"]
    rows, src = None, ""
    if LIVE:
        try:
            rows, src = _nse(symbol, start, end), "NSE"
        except Exception:
            rows = None
    if rows is None:
        snap = load(symbol) or {}
        rows = [dict(a, source="BSE via Screener snapshot") for a in snap.get("announcements", [])]
        src = "snapshot"
    else:
        store.put(k, {"rows": rows, "src": src})
    return rows, src
