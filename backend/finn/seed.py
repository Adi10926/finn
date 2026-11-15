"""Parse the Screener snapshot files in data/raw/*.md.

Format: sections introduced by '## name'. Table sections are CSV with a 'Metric,<periods>'
header. 'meta' is key,value. 'concalls'/'annual_reports' are 'label,url'.
'announcements' are 'YYYY-MM-DD|title|desc|url'.

The live Screener adapter (sources/screener.py) emits exactly the same dict shape, so the
whole pipeline is agnostic to whether data came from the snapshot or a live fetch.
"""
from __future__ import annotations

from functools import lru_cache

from .config import RAW

TABLES = {"quarters", "annual", "balance", "cashflow", "ratios"}

# normalise row labels so banks / non-banks / live HTML all map to the same keys
ALIASES = {
    "sales": "sales", "revenue": "sales",
    "expenses": "expenses",
    "operating profit": "op", "financing profit": "op",
    "other income": "other_income",
    "interest": "interest",
    "depreciation": "depreciation",
    "profit before tax": "pbt",
    "net profit": "pat",
    "dividend payout %": "payout",
    "equity capital": "equity", "reserves": "reserves",
    "borrowings": "borrowings", "borrowing": "borrowings", "deposits": "deposits",
    "other liabilities": "other_liab", "total liabilities": "total_liab",
    "fixed assets": "fixed_assets", "cwip": "cwip", "investments": "investments",
    "other assets": "other_assets",
    "cash from operating activity": "cfo", "cash from investing activity": "cfi",
    "cash from financing activity": "cff", "free cash flow": "fcf",
    "debtor days": "debtor_days", "inventory days": "inventory_days",
    "days payable": "payable_days", "cash conversion cycle": "ccc",
    "working capital days": "wc_days", "roce %": "roce", "roe %": "roe",
}


def _num(x: str):
    x = x.strip().replace("%", "").replace(",", "")
    if x in ("", "-", "—"):
        return None
    try:
        return float(x)
    except ValueError:
        return None


def parse_text(text: str) -> dict:
    out: dict = {"meta": {}, "announcements": [], "concalls": [], "annual_reports": []}
    sec = None
    header = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            sec = line[3:].strip()
            header = None
            if sec in TABLES:
                out[sec] = {"periods": [], "rows": {}}
            continue
        if sec in TABLES:
            cells = [c.strip() for c in line.split(",")]
            if cells[0].lower() == "metric":
                out[sec]["periods"] = cells[1:]
                header = cells[1:]
                continue
            k = ALIASES.get(cells[0].lower().rstrip(" +"))
            if k and header is not None:
                vals = [_num(c) for c in cells[1:]]
                vals += [None] * (len(header) - len(vals))
                out[sec]["rows"][k] = vals[: len(header)]
        elif sec == "meta":
            k, _, v = line.partition(",")
            out["meta"][k.strip()] = v.strip()
        elif sec in ("concalls", "annual_reports"):
            k, _, v = line.partition(",")
            if v.startswith("http"):
                out[sec].append({"label": k.strip(), "url": v.strip()})
        elif sec == "announcements":
            p = [s.strip() for s in line.split("|")]
            if len(p) >= 4:
                out["announcements"].append({"date": p[0], "title": p[1], "desc": p[2], "url": p[3]})
    m = out["meta"]
    for f in ("price", "mcap", "pe", "roce", "roe"):
        if f in m:
            m[f] = _num(m[f])
    m["kind"] = m.get("kind", "corporate")
    return out


@lru_cache(maxsize=None)
def load(symbol: str) -> dict | None:
    p = RAW / f"{symbol.upper()}.md"
    if not p.exists():
        return None
    d = parse_text(p.read_text())
    d["symbol"] = symbol.upper()
    d["source"] = "screener-snapshot"
    return d


def available() -> list[str]:
    return sorted(p.stem for p in RAW.glob("*.md"))
