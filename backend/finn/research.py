"""Pull-side research, grounded ONLY in primary data (filed financials, transcripts, ARs).

Design: numbers first, language last.
  1. Deterministic analytics over the statements (growth, margins, leverage, WC cycle, cash
     conversion) -> every claim carries the table it came from.
  2. Guidance ledger extracted from concall transcripts (cheap model, chunk-filtered, cached).
  3. Deterministic checks of guidance vs. reported numbers (run-rate tests, margin paths).
  4. Bull/bear assembled from 1-3. With a 'reason' model available we let it rewrite the
     bull/bear and verdicts into tighter prose — constrained to the facts we pass it.
No news, broker notes or model world-knowledge enter this path.
"""
from __future__ import annotations

import json
from functools import lru_cache

from . import llm
from .config import DATA
from .results import headline, ttm_sales
from .sources import documents

SRC_Q = "Quarterly results (Screener, consolidated)"
SRC_A = "Annual P&L (Screener, consolidated)"
SRC_B = "Balance sheet (Screener)"
SRC_C = "Cash-flow statement (Screener)"
SRC_R = "Ratios (Screener)"


def _row(c, sec, k):
    return (c.get(sec, {}).get("rows", {}) or {}).get(k)


def _periods(c, sec):
    return c.get(sec, {}).get("periods", [])


def _cagr(series, years):
    s = [v for v in (series or []) if v is not None]
    if len(s) <= years or s[-1 - years] <= 0 or s[-1] <= 0:
        return None
    return round(((s[-1] / s[-1 - years]) ** (1 / years) - 1) * 100, 1)


def _fy_only(c, sec):
    """Drop TTM / half-year columns so CAGRs use fiscal years."""
    P = _periods(c, sec)
    idx = [i for i, p in enumerate(P) if p.lower().startswith("mar")]
    return idx


@lru_cache(maxsize=1)
def _ledgers() -> dict:
    p = DATA / "ledgers.json"
    return json.loads(p.read_text()) if p.exists() else {}


# ---------------------------------------------------------------------------------- sections

def snapshot(c):
    m = c.get("meta", {})
    return {"name": m.get("name"), "sector": m.get("sector"), "about": m.get("about"),
            "kind": m.get("kind"), "price": m.get("price"), "mcap": m.get("mcap"),
            "pe": m.get("pe"), "roce": m.get("roce"), "roe": m.get("roe"),
            "segments": None, "segments_note": "Segment mix is read from the annual report when a model key is set.",
            "src": "Screener company page"}


def financials(c):
    hl = headline(c)
    q = c.get("quarters", {}).get("rows", {})
    out = {"latest": hl, "src": SRC_Q}
    if q.get("sales") and len(q["sales"]) >= 4:
        t = lambda k: sum(v for v in (q.get(k) or [0])[-4:] if v is not None) if q.get(k) else None
        rev, op, pat = t("sales"), t("op"), t("pat")
        out["ttm"] = {"revenue": rev, "ebitda": op if c["meta"].get("kind") != "bank" else None, "pat": pat,
                      "ebitda_margin": round(op / rev * 100, 1) if rev and op and c["meta"].get("kind") != "bank" else None,
                      "pat_margin": round(pat / rev * 100, 1) if rev and pat else None}
    return out


def trajectory(c):
    idx = _fy_only(c, "annual")
    if not idx:
        return None
    P = [_periods(c, "annual")[i] for i in idx]
    pick = lambda k: [(_row(c, "annual", k) or [None] * 99)[i] for i in idx]
    sales, op, pat = pick("sales"), pick("op"), pick("pat")
    bank = c["meta"].get("kind") == "bank"
    opm = [round(o / s * 100, 1) if (o is not None and s) else None for o, s in zip(op, sales)]
    lines = []
    s3, s5, p3 = _cagr(sales, 3), _cagr(sales, 5), _cagr(pat, 3)
    if s3 is not None:
        lines.append({"text": f"Revenue CAGR {s3}% (3y), {s5 if s5 is not None else '—'}% (5y)",
                      "tone": "good" if s3 >= 15 else "bad" if s3 < 5 else "neutral"})
    if p3 is not None:
        lines.append({"text": f"PAT CAGR {p3}% (3y)", "tone": "good" if p3 >= 15 else "bad" if p3 < 5 else "neutral"})
    if not bank and len([x for x in opm if x is not None]) >= 4:
        d = opm[-1] - opm[-4]
        lines.append({"text": f"EBITDA margin {opm[-1]}% vs {opm[-4]}% three years ago ({d * 100:+.0f} bps)",
                      "tone": "good" if d > 1 else "bad" if d < -1 else "neutral"})
    growing = [n for n, v in (("revenue", s3), ("profit", p3)) if v is not None and v >= 10]
    compress = not bank and len(opm) >= 4 and opm[-1] is not None and opm[-4] is not None and opm[-1] < opm[-4] - 1
    verdict = (("Growing: " + " and ".join(growing)) if growing else "Low growth") + \
              ("; margins compressing" if compress else "; margins holding" if not bank else "")
    return {"periods": P, "sales": sales, "pat": pat, "opm": None if bank else opm,
            "lines": lines, "verdict": verdict, "src": SRC_A}


def balance(c):
    idx = _fy_only(c, "balance") or list(range(len(_periods(c, "balance"))))
    if not idx:
        return None
    P = [_periods(c, "balance")[i] for i in idx]
    g = lambda sec, k: [(_row(c, sec, k) or [None] * 99)[i] if i < len(_row(c, sec, k) or []) else None for i in idx]
    eq, res, debt = g("balance", "equity"), g("balance", "reserves"), g("balance", "borrowings")
    nw = [(e or 0) + (r or 0) if e is not None else None for e, r in zip(eq, res)]
    de = [round(d / n, 2) if (d is not None and n) else None for d, n in zip(debt, nw)]
    bank = c["meta"].get("kind") == "bank"
    lines = []
    if bank:
        dep = g("balance", "deposits")
        if dep[-1] and dep[-2]:
            lines.append({"text": f"Deposits ₹{dep[-1]:,.0f} Cr ({(dep[-1] / dep[-2] - 1) * 100:+.1f}% YoY)", "tone": "neutral"})
        lines.append({"text": "Leverage, working-capital and cash-conversion ratios do not apply to lenders. "
                              "Capital adequacy and asset quality are read from the annual report.", "tone": "neutral"})
        return {"periods": P, "net_worth": nw, "borrowings": debt, "de": None, "lines": lines, "src": SRC_B, "wc": None}
    if de[-1] is not None:
        lines.append({"text": f"Debt/Equity {de[-1]}× (borrowings ₹{debt[-1]:,.0f} Cr vs net worth ₹{nw[-1]:,.0f} Cr)",
                      "tone": "good" if de[-1] < 0.3 else "bad" if de[-1] > 1 else "neutral"})
    ridx = _fy_only(c, "ratios")
    rr = lambda k: [(_row(c, "ratios", k) or [None] * 99)[i] for i in ridx] if _row(c, "ratios", k) else None
    wc = {"periods": [_periods(c, "ratios")[i] for i in ridx], "debtor": rr("debtor_days"),
          "inventory": rr("inventory_days"), "payable": rr("payable_days"), "ccc": rr("ccc"), "wc": rr("wc_days")}
    if wc["ccc"] and len(wc["ccc"]) >= 4 and wc["ccc"][-1] is not None and wc["ccc"][-4] is not None:
        d = wc["ccc"][-1] - wc["ccc"][-4]
        lines.append({"text": f"Cash conversion cycle {wc['ccc'][-1]:.0f} days vs {wc['ccc'][-4]:.0f} three years ago",
                      "tone": "bad" if d > 15 else "good" if d < -10 else "neutral"})
    if wc["debtor"] and len(wc["debtor"]) >= 4 and wc["debtor"][-1] and wc["debtor"][-4] and wc["debtor"][-1] - wc["debtor"][-4] > 10:
        lines.append({"text": f"Debtor days up from {wc['debtor'][-4]:.0f} to {wc['debtor'][-1]:.0f}. Customers are paying slower.", "tone": "bad"})
    cw, fa = g("balance", "cwip"), g("balance", "fixed_assets")
    if cw[-1] and fa[-1] and cw[-1] / fa[-1] > 0.15:
        lines.append({"text": f"CWIP ₹{cw[-1]:,.0f} Cr = {cw[-1] / fa[-1] * 100:.0f}% of fixed assets, so a capex cycle is underway", "tone": "neutral"})
    return {"periods": P, "net_worth": nw, "borrowings": debt, "de": de, "wc": wc, "lines": lines, "src": f"{SRC_B}; {SRC_R}"}


def cash(c):
    if c["meta"].get("kind") == "bank":
        return {"lines": [{"text": "Operating cash flow at a bank mostly reflects deposit and loan flows, "
                                   "so profit-to-cash conversion is not a useful test.", "tone": "neutral"}], "src": SRC_C}
    cidx = _fy_only(c, "cashflow")
    if not cidx:
        return None
    P = [_periods(c, "cashflow")[i] for i in cidx]
    cfo = [(_row(c, "cashflow", "cfo") or [None] * 99)[i] for i in cidx]
    fcf = [(_row(c, "cashflow", "fcf") or [None] * 99)[i] for i in cidx] if _row(c, "cashflow", "fcf") else None
    aP = _periods(c, "annual")
    pat_by = {p: v for p, v in zip(aP, _row(c, "annual", "pat") or [])}
    op_by = {p: v for p, v in zip(aP, _row(c, "annual", "op") or [])}
    conv = [round(cf / pat_by[p], 2) if (cf is not None and pat_by.get(p)) else None for p, cf in zip(P, cfo)]
    conv_e = [round(cf / op_by[p], 2) if (cf is not None and op_by.get(p)) else None for p, cf in zip(P, cfo)]
    n = min(5, len(P))
    s_cfo = sum(v for v in cfo[-n:] if v is not None)
    s_pat = sum(pat_by.get(p) or 0 for p in P[-n:])
    cum = round(s_cfo / s_pat, 2) if s_pat else None
    lines = []
    if cum is not None:
        lines.append({"text": f"{n}-year cumulative CFO/PAT = {cum}×. " +
                      ("Profits are turning into cash." if cum >= 0.9 else "Cash is lagging reported profit. Check receivables and inventory." if cum < 0.7 else "Conversion is adequate."),
                      "tone": "good" if cum >= 0.9 else "bad" if cum < 0.7 else "neutral"})
    if fcf and len(fcf) >= 3:
        neg = sum(1 for v in fcf[-5:] if v is not None and v < 0)
        lines.append({"text": f"Free cash flow ₹{fcf[-1]:,.0f} Cr latest year; negative in {neg} of last {min(5, len(fcf))} years",
                      "tone": "bad" if neg >= 2 else "good" if neg == 0 else "neutral"})
    return {"periods": P, "cfo": cfo, "fcf": fcf, "cfo_pat": conv, "cfo_ebitda": conv_e, "cum": cum,
            "lines": lines, "src": f"{SRC_C}; {SRC_A}"}


# ---------------------------------------------------------------------- guidance & narrative

LEDGER_PROMPT = """You are extracting management guidance from an Indian company's earnings-call transcript.
Return JSON {{"guidance":[{{"metric":"revenue|margin|volume|capex|other","statement":"<tight paraphrase with numbers>","period":"..","speaker":".."}}],
"delivered":[{{"metric":"..","statement":"<what management reported for the quarter>"}}],"analyst_pushback":["<topic>"],"tone":"<one word>"}}.
Only explicit forward-looking statements with numbers or clear direction. Ignore safe-harbour boilerplate.
Transcript excerpt:
{chunk}"""


def ledger_from_transcripts(c) -> dict | None:
    """Live path: cheap model over forward-looking chunks of the latest transcript; merged + cached."""
    if not llm.available() or not c.get("concalls"):
        return None
    call = c["concalls"][0]
    text = documents.pdf_text(call["url"])
    if not text:
        return None
    parts = documents.forward_looking(text)[:6]
    merged = {"guidance": [], "delivered": [], "analyst_pushback": [], "tone": None,
              "source": {"title": f"{c['meta'].get('name')} concall {call['label']}", "url": call["url"]},
              "extracted_by": "flash-lite over filtered chunks"}
    for ch in parts:
        r = llm.call("extract", LEDGER_PROMPT.format(chunk=ch))
        if isinstance(r, dict):
            for k in ("guidance", "delivered", "analyst_pushback"):
                merged[k] += r.get(k) or []
            merged["tone"] = merged["tone"] or r.get("tone")
    return merged if merged["guidance"] else None


def _checks(c, led):
    """Deterministic promise-vs-numbers tests."""
    out = []
    q = c.get("quarters", {}).get("rows", {})
    bank = c["meta"].get("kind") == "bank"
    for gd in led.get("guidance", []):
        ck = gd.get("check") or {}
        if ck.get("type") == "run_rate":
            ann = ck["actual_q"] * 4
            v = "ahead" if ann > ck["target_fy"] * 1.1 else "on track" if ann > ck["target_fy"] * 0.9 else "behind"
            out.append({"promise": gd["statement"], "test": f"{ck['label']} × 4 = ₹{ann:,.0f} Cr annualised vs ₹{ck['target_fy']:,} Cr guided",
                        "verdict": v, "tone": "good" if v != "behind" else "bad"})
        elif ck.get("type") == "capex_vs_history":
            fa, cw = _row(c, "balance", "fixed_assets"), _row(c, "balance", "cwip")
            if fa and cw and len(fa) >= 2:
                hist = (fa[-1] + cw[-1]) - (fa[-2] + cw[-2])
                out.append({"promise": gd["statement"], "test": f"Gross block + CWIP grew ₹{hist:,.0f} Cr last FY vs ₹{ck['target_fy']:,} Cr guided for FY27",
                            "verdict": "consistent" if abs(hist - ck["target_fy"]) / ck["target_fy"] < 0.5 else "step-change",
                            "tone": "neutral"})
        elif ck.get("type") == "margin_path" and q.get("sales") and not bank:
            s, o = q["sales"], q["op"]
            now, ya = o[-1] / s[-1] * 100, o[-5] / s[-5] * 100
            lost = (ya - now) * 100
            out.append({"promise": gd["statement"],
                        "test": f"Quarterly EBITDA margin is {now:.2f}% vs {ya:.2f}% a year ago ({-lost:+.0f} bps)",
                        "verdict": "unproven: margin is still falling" if lost > 0 else "on track", "tone": "bad" if lost > 0 else "good"})
    # narrative claims vs numbers
    hl = headline(c)
    if hl and led.get("tone"):
        pat = next((m for m in hl["metrics"] if m["key"] == "pat"), {})
        rev = next((m for m in hl["metrics"] if m["key"] == "sales"), {})
        if pat.get("yoy") is not None and pat["yoy"] < -20:
            out.append({"promise": f"Management tone on the call: {led['tone']}",
                        "test": f"Reported PAT {pat['yoy']:+.0f}% YoY on revenue {rev.get('yoy', 0):+.0f}%",
                        "verdict": "diverges", "tone": "bad"})
    for d in led.get("delivered", []):
        if "pass-through" in d.get("statement", "") and q.get("op"):
            op_yoy = (q["op"][-1] / q["op"][-5] - 1) * 100
            rev_yoy = (q["sales"][-1] / q["sales"][-5] - 1) * 100
            out.append({"promise": "Management: growth came from price pass-through, not volume",
                        "test": f"Revenue {rev_yoy:+.0f}% YoY, EBITDA only {op_yoy:+.0f}%",
                        "verdict": "agrees, which is the problem: pass-through earns almost no margin", "tone": "bad"})
    return out


def guidance(c):
    led = _ledgers().get(c["symbol"]) or ledger_from_transcripts(c)
    calls = [{"label": x["label"], "url": x["url"]} for x in c.get("concalls", [])][:4]
    if not led:
        return {"available": False, "transcripts": calls,
                "note": "No guidance ledger yet. Set GEMINI_API_KEY and FINN extracts it from the transcripts listed below (cheap model, cached)."}
    return {"available": True, **led, "checks": _checks(c, led), "transcripts": calls}


def bull_bear(c, tr, bs, cs, gd):
    bull, bear = [], []
    m = c.get("meta", {})
    for sec in (tr, bs, cs):
        for ln in (sec or {}).get("lines", []):
            (bull if ln["tone"] == "good" else bear if ln["tone"] == "bad" else []).append({"text": ln["text"], "src": sec["src"]})
    hl = headline(c)
    for f in (hl or {}).get("flags", []):
        (bull if f["tone"] == "good" else bear if f["tone"] == "bad" else []).append({"text": f["text"], "src": SRC_Q})
    if m.get("roce") and m["roce"] >= 20 and m.get("kind") != "bank":
        bull.append({"text": f"ROCE {m['roce']:.0f}%: high return on capital", "src": "Screener ratios"})
    if m.get("pe") and m["pe"] > 50:
        g3 = _cagr([v for v in (_row(c, "annual", "pat") or [])], 3)
        bear.append({"text": f"P/E {m['pe']:.0f}× already prices in a lot" + (f" (3y PAT CAGR {g3}%)" if g3 else ""), "src": "Screener ratios"})
    for ck in (gd or {}).get("checks", []):
        (bull if ck["tone"] == "good" else bear if ck["tone"] == "bad" else []).append({"text": f"{ck['test']}: {ck['verdict']}", "src": "Concall vs filed numbers"})
    def dedupe(xs):
        import re as _re
        seen, keep = [], []
        for x in xs:
            nums = set(_re.findall(r"-?\d+(?:\.\d+)?", x["text"]))
            if any(len(nums & s) >= 2 for s in seen):
                continue
            seen.append(nums)
            keep.append(x)
        return keep
    bull, bear = dedupe(bull), dedupe(bear)
    out = {"bull": bull[:5], "bear": bear[:5], "method": "rules over filed numbers"}
    if llm.available() and (bull or bear):
        r = llm.call("reason", "Rewrite into a tight bull case and bear case (max 4 bullets each, <=18 words each) "
                               "using ONLY these facts. Do not add outside knowledge. JSON {bull:[..],bear:[..]}.\n"
                               + json.dumps({"bull": [b["text"] for b in bull], "bear": [b["text"] for b in bear]}))
        if isinstance(r, dict) and r.get("bull"):
            out.update(bull_prose=r["bull"], bear_prose=r.get("bear", []), method="rules + flash rewrite (facts-only)")
    return out


def dossier(c: dict) -> dict:
    c = dict(c)
    c["ttm_sales"] = ttm_sales(c)
    tr, bs, cs = trajectory(c), balance(c), cash(c)
    gd = guidance(c)
    return {"symbol": c["symbol"], "source": c.get("source"), "snapshot": snapshot(c),
            "financials": financials(c), "trajectory": tr, "balance": bs, "cash": cs,
            "guidance": gd, "bullbear": bull_bear(c, tr, bs, cs, gd),
            "coverage": {k: bool(c.get(k)) for k in ("quarters", "annual", "balance", "cashflow", "ratios")}}
