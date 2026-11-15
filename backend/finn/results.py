"""Quarterly results first cut: Revenue, EBITDA, PBT, PAT — QoQ and YoY — plus quality flags.

Source of numbers: the company's results filing as tabulated on Screener (live) or the
snapshot. With an LLM key, `from_filing()` can also read the raw results PDF (cheap model)
and we cross-check the two; disagreements are surfaced, never averaged.
"""
from __future__ import annotations


def _pct(a, b):
    if a is None or b in (None, 0):
        return None
    return round((a - b) / abs(b) * 100, 1)


def headline(company: dict) -> dict | None:
    q = company.get("quarters")
    if not q or not q.get("rows", {}).get("sales"):
        return None
    P, R = q["periods"], q["rows"]
    n = len(P)
    if n < 2:
        return None
    i, j, y = n - 1, n - 2, n - 5 if n >= 5 else None
    bank = company.get("meta", {}).get("kind") == "bank"

    def g(k, idx):
        v = R.get(k)
        return v[idx] if v and idx is not None and idx < len(v) else None

    metrics = []
    for key, label in (("sales", "Revenue"), ("op", "EBITDA"), ("pbt", "PBT"), ("pat", "PAT")):
        if bank and key == "op":
            metrics.append({"key": key, "label": "EBITDA", "na": "Not meaningful for lenders. Use PBT and PAT."})
            continue
        cur, prev, yago = g(key, i), g(key, j), g(key, y)
        metrics.append({"key": key, "label": label, "cur": cur, "prev": prev, "yago": yago,
                        "qoq": _pct(cur, prev), "yoy": _pct(cur, yago)})
    flags = []
    s, op, oi, pbt = g("sales", i), g("op", i), g("other_income", i), g("pbt", i)
    if not bank and s and op is not None:
        m_now = op / s * 100
        s_y, op_y = g("sales", y), g("op", y)
        if s_y and op_y is not None:
            m_y = op_y / s_y * 100
            d = (m_now - m_y) * 100
            flags.append({"kind": "margin", "text": f"EBITDA margin {m_now:.1f}% vs {m_y:.1f}% a year ago ({d:+.0f} bps)",
                          "tone": "bad" if d < -50 else "good" if d > 50 else "neutral"})
    if oi is not None and pbt and pbt > 0 and oi / pbt > 0.25:
        flags.append({"kind": "quality", "text": f"Other income is {oi / pbt * 100:.0f}% of PBT. Profit leans on non-operating items.",
                      "tone": "bad"})
    pat_yoy = metrics[3].get("yoy")
    rev_yoy = metrics[0].get("yoy")
    if pat_yoy is not None and rev_yoy is not None and rev_yoy > 10 and pat_yoy < -10:
        flags.append({"kind": "divergence", "text": f"Revenue {rev_yoy:+.0f}% but PAT {pat_yoy:+.0f}% YoY. Growth is not reaching the bottom line.",
                      "tone": "bad"})
    spark = {k: [v for v in (R.get(k) or [])][-8:] for k in ("sales", "pat")}
    return {"quarter": P[i], "prev_quarter": P[j], "yago_quarter": P[y] if y is not None else None,
            "metrics": metrics, "flags": flags, "spark": spark, "periods": P[-8:],
            "unit": "₹ Cr", "basis": "Consolidated"}


def ttm_sales(company: dict) -> float | None:
    q = company.get("quarters", {}).get("rows", {}).get("sales")
    if q and len(q) >= 4 and all(v is not None for v in q[-4:]):
        return sum(q[-4:])
    a = company.get("annual", {})
    if a.get("rows", {}).get("sales"):
        return a["rows"]["sales"][-1]
    return None
