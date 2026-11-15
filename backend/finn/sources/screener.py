"""Live Screener.in adapter — fundamentals for ANY listed ticker.

Parses the public company page (consolidated, falling back to standalone) into the same
dict shape as seed.parse_text, so research works on tickers we never pre-loaded.
"""
from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

from .. import store
from ..config import LIVE, USER_AGENT
from ..seed import ALIASES, _num, load

BASE = "https://www.screener.in/company/{s}/{v}"
SECTION_IDS = {"quarters": "quarters", "annual": "profit-loss", "balance": "balance-sheet",
               "cashflow": "cash-flow", "ratios": "ratios"}


def _table(soup, sec_id):
    sec = soup.find("section", id=sec_id)
    if not sec:
        return None
    t = sec.find("table", class_="data-table")
    if not t:
        return None
    periods = [th.get_text(strip=True) for th in t.find("thead").find_all("th")][1:]
    rows = {}
    for tr in t.find("tbody").find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        label = re.sub(r"\s*\+\s*$", "", tds[0].get_text(" ", strip=True)).lower()
        k = ALIASES.get(label)
        if k:
            rows[k] = [_num(td.get_text(strip=True)) for td in tds[1:]]
    return {"periods": periods, "rows": rows}


def _parse(html: str, symbol: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    out = {"symbol": symbol, "source": "screener-live", "meta": {"kind": "corporate"},
           "announcements": [], "concalls": [], "annual_reports": []}
    h1 = soup.find("h1")
    out["meta"]["name"] = h1.get_text(strip=True) if h1 else symbol
    for li in soup.select("#top-ratios li"):
        name = li.find("span", class_="name")
        val = li.find("span", class_="number")
        if name and val:
            n = name.get_text(strip=True).lower()
            key = {"current price": "price", "market cap": "mcap", "stock p/e": "pe",
                   "roce": "roce", "roe": "roe"}.get(n)
            if key:
                out["meta"][key] = _num(val.get_text(strip=True))
    about = soup.select_one(".company-profile .about p") or soup.select_one(".about p")
    out["meta"]["about"] = about.get_text(" ", strip=True)[:400] if about else ""
    for k, sid in SECTION_IDS.items():
        t = _table(soup, sid)
        if t:
            out[k] = t
    if "quarters" in out and "op" not in out["quarters"]["rows"]:
        pass
    if "financing profit" in html.lower():
        out["meta"]["kind"] = "bank"
    for a in soup.select(".documents.annual-reports a"):
        out["annual_reports"].append({"label": a.get_text(" ", strip=True)[:40], "url": a.get("href")})
    for li in soup.select(".documents.concalls li"):
        label = li.find("div")
        tr = li.find("a", string=re.compile("Transcript", re.I))
        if tr:
            out["concalls"].append({"label": label.get_text(strip=True) if label else "",
                                    "url": tr.get("href")})
    for li in soup.select("#company-announcements li, .documents.flex-column li")[:20]:
        a = li.find("a")
        if a and a.get("href", "").startswith("http"):
            out["announcements"].append({"date": "", "title": a.get_text(" ", strip=True)[:160],
                                         "desc": "", "url": a["href"]})
    return out


def fundamentals(symbol: str) -> dict | None:
    symbol = symbol.upper()
    k = store.key("screener", symbol)
    hit = store.get(k, ttl=24 * 3600)
    if hit:
        return hit
    if LIVE:
        for v in ("consolidated/", ""):
            try:
                r = httpx.get(BASE.format(s=symbol, v=v), headers={"User-Agent": USER_AGENT},
                              timeout=20, follow_redirects=True)
                if r.status_code == 200 and "data-table" in r.text:
                    d = _parse(r.text, symbol)
                    if d.get("quarters", {}).get("rows"):
                        store.put(k, d)
                        return d
            except Exception:
                break
    return load(symbol)
