"""Assemble the push feed, alerts and portfolio view."""
from __future__ import annotations

import datetime as dt
import re

from . import enrich, store
from .alerts import eod_alerts
from .config import AS_OF, DEFAULTS, PORTFOLIO, RESEARCH_SET
from .research import dossier
from .results import headline, ttm_sales
from .seed import load
from .sources import announcements, prices, screener
from .taxonomy import score


def as_of() -> dt.date:
    return dt.date.fromisoformat(AS_OF) if AS_OF else dt.date.today()


def company(symbol: str) -> dict | None:
    c = screener.fundamentals(symbol) or load(symbol)
    if c:
        c = dict(c)
        c["ttm_sales"] = ttm_sales(c)
    return c


def _dedupe(items):
    """Merge filings that describe the same event (e.g. board approval + RBI approval)."""
    seen = {}
    for it in sorted(items, key=lambda x: -x["score"]):
        person = (it["facts"].get("person") or "").lower()
        if person:
            k = (it["symbol"], it["category"], person)
        elif it["category"] in ("results", "press_release", "earnings_call", "investor_meetings"):
            k = (it["symbol"], it["category"], it["date"])   # results + deck + letter on one day = one event
        else:
            k = (it["symbol"], it["url"])
        if k in seen:
            seen[k]["related"].append({"title": it["title"], "date": it["date"], "url": it["url"]})
        else:
            it["related"] = []
            seen[k] = it
    return list(seen.values())


def feed(today: dt.date, days: int = 30, care=None) -> list[dict]:
    care = care or DEFAULTS["care_categories"]
    out = []
    for sym in PORTFOLIO:
        c = company(sym)
        if not c:
            continue
        rows, src = announcements.fetch(sym, today - dt.timedelta(days=days), today)
        hl = headline(c)
        for a in rows:
            sc = score(a, c, care)
            it = {"symbol": sym, "name": c["meta"].get("name", sym), **a, **sc, "feed_source": src}
            if sc["category"] == "results" and hl:
                it["results"] = hl
                yoy = {m["key"]: m.get("yoy") for m in hl["metrics"]}
                it["why"] = (f"{hl['quarter']}: revenue {yoy['sales']:+.0f}% YoY, PAT {yoy['pat']:+.0f}% YoY"
                             if yoy.get("sales") is not None and yoy.get("pat") is not None else "Results filed")
            if sc["category"] == "management_change" and sc["facts"].get("level") == "top" \
                    and sc["facts"].get("event") == "appointment":
                it["bio"] = enrich.bio(sc["facts"].get("person"), c["meta"].get("name", sym))
            out.append(it)
    out = _dedupe(out)
    out.sort(key=lambda x: (x["date"], x["score"]), reverse=True)
    return out


def portfolio(today: dt.date) -> list[dict]:
    rows = []
    for sym, h in PORTFOLIO.items():
        c = company(sym)
        if not c:
            continue
        m = c["meta"]
        e = prices.eod(sym, m.get("price"), today)
        s = e["series"]
        last, prev = s[-1], s[-2]
        avg = sum(d["volume"] for d in s[-21:-1]) / 20
        rows.append({"symbol": sym, "name": m.get("name"), "sector": h["sector"], "qty": h["qty"],
                     "price": last["close"], "chg_pct": round((last["close"] / prev["close"] - 1) * 100, 2),
                     "vol_mult": round(last["volume"] / avg, 2) if avg else None,
                     "value": round(last["close"] * h["qty"]), "mcap": m.get("mcap"), "pe": m.get("pe"),
                     "series": s, "simulated": e["simulated"], "price_source": e["source"],
                     "results": headline(c), "kind": m.get("kind")})
    return rows


def bundle(care=None) -> dict:
    today = as_of()
    port = portfolio(today)
    items = feed(today, care=care)
    research = {}
    for sym in sorted(set(RESEARCH_SET) | set(PORTFOLIO)):
        c = company(sym)
        if c:
            research[sym] = dossier(c)
    eod = {p["symbol"]: eod_alerts(p["series"], DEFAULTS["volume_multiple"], DEFAULTS["volume_lookback"],
                                    DEFAULTS["price_move_pct"]) for p in port}
    return {"as_of": today.isoformat(), "generated": dt.datetime.now().isoformat(timespec="seconds"),
            "defaults": DEFAULTS, "portfolio": port, "feed": items, "eod_alerts": eod,
            "research": research, "research_set": RESEARCH_SET,
            "data_modes": {"prices": "simulated" if any(p["simulated"] for p in port) else "yahoo",
                           "filings": items[0]["feed_source"] if items else "none",
                           "fundamentals": "screener"},
            "llm_usage": store.llm_usage()}


ASK_INTENTS = [
    ("guidance", r"promis|guid|deliver|narrative|said|management|concall|call"),
    ("cash", r"cash|convert|fcf|cfo|quality"),
    ("balance", r"debt|leverage|balance|working capital|wc|borrow"),
    ("trajectory", r"trend|trajector|growth|grow|margin|multi-?year"),
    ("bullbear", r"bull|bear|case|thesis|buy|sell|should"),
    ("financials", r"result|quarter|number|revenue|profit|pat|ebitda|snapshot"),
]


def parse_ask(q: str, known: list[str]) -> dict:
    up = q.upper()
    sym = next((s for s in sorted(known, key=len, reverse=True) if re.search(rf"\b{re.escape(s)}\b", up)), None)
    if not sym:
        m = re.search(r"\b([A-Z][A-Z&\-]{2,14})\b", q)
        sym = m.group(1) if m else None
    intent = next((name for name, rx in ASK_INTENTS if re.search(rx, q, re.I)), "all")
    return {"symbol": sym, "intent": intent}
