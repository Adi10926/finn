"""Classify an exchange filing and decide how much attention it deserves.

Deterministic on purpose: ~95% of filings are classifiable from the subject line, and the
judgement 'how material is this for THIS company' is arithmetic (order size vs revenue,
issue size vs market cap, who exactly is leaving). An LLM is only consulted for filings
that match nothing (category 'unclassified' with no routine marker) — and only if a key exists.
"""
from __future__ import annotations

import re

from . import llm

# Ordered: first match wins. Specific patterns come before generic ones.
RULES: list[tuple[str, str]] = [
    ("earnings_call",     r"transcript|conference call|earnings call|audio recording|con\.? ?call"),
    ("results_ad",        r"newspaper publication.*result|newspaper.*result|publication of.*result"),
    ("results",           r"financial result|results for the quarter|unaudited.*result|audited.*result|"
                          r"shareholders'? letter|investor presentation|outcome of board meeting.*result"),
    ("insider_trading",   r"\bSAST\b|reg(ulation)?\.? ?29|reg(ulation)?\.? ?7\(?2|insider|promoter .*(sold|sell|bought|acquire)"),
    ("pledging",          r"pledge|encumbrance"),
    ("fund_raise",        r"\bQIP\b|qualified institution|rights issue|preferential|warrant|buy-?back|"
                          r"commercial paper|\bNCDs?\b|debenture|fund ?rais"),
    ("M&A",               r"acquisition|acquire|amalgamation|merger|demerger|scheme of arrangement|"
                          r"joint venture|\bJV\b|stake (sale|purchase)|share swap|restructuring|divest"),
    ("management_change", r"change in (directorate|management)|appoint|resign|cessation|superannuat|"
                          r"re-?appoint|retire|\bMD\b|\bCEO\b|\bCFO\b|chairman|key managerial"),
    ("credit_rating",     r"credit rating|\brating\b"),
    ("litigation",        r"penalt|\bfine\b|NCLT|NCLAT|CIRP|insolvency|show cause|tax demand|"
                          r"litigation|SEBI order|court|tribunal|adjudicat"),
    ("dividend",          r"dividend|record date"),
    ("bonus_split",       r"\bbonus\b|split|sub-?division"),
    ("capex",             r"capacity|expansion|new plant|greenfield|brownfield|capex|commission(ed|ing)"),
    ("order_win",         r"bagging|order(s)? (win|received|bagged)|receiving of order|contract(s)? (win|award)|"
                          r"\bwon\b.*order"),
    ("press_release",     r"press release|launch|partnership|collaborat|clarif|rumou?r|verification"),
    ("investor_meetings", r"analyst|investor meet|investor conference|roadshow|\bNDR\b|institutional investor"),
    ("postal_ballot",     r"postal ballot|scrutini[sz]er"),
    ("agm_egm",           r"\bAGM\b|\bEGM\b|general meeting"),
    ("fund_use",          r"utili[sz]ation of (issue )?proceeds|statement of deviation"),
    ("unclassified",      r"ESOP|ESPS|newspaper|registrar|\bRTA\b|KFin|demateriali|compliance|"
                          r"certificate|ESG|prize|award|loss of share|trading window|investor complaint"),
]
COMPILED = [(c, re.compile(p, re.I)) for c, p in RULES]

LABEL = {
    "results": "Results", "results_ad": "Results ad", "M&A": "M&A", "fund_raise": "Fund raise",
    "management_change": "Management", "litigation": "Legal / Regulatory",
    "insider_trading": "Insider / Promoter", "earnings_call": "Earnings call",
    "investor_meetings": "Investor meets", "credit_rating": "Credit rating", "dividend": "Dividend",
    "bonus_split": "Bonus / Split", "capex": "Capex", "press_release": "Press release",
    "order_win": "Order win", "postal_ballot": "Postal ballot", "agm_egm": "AGM / EGM",
    "pledging": "Pledge", "fund_use": "Use of proceeds", "unclassified": "Routine",
}
# category -> the reference taxonomy bucket (for filters the brief describes)
BUCKET = {"results_ad": "results", "order_win": "press_release", "fund_use": "fund_raise"}

BASE = {
    "results": 80, "M&A": 72, "fund_raise": 72, "management_change": 66, "litigation": 62,
    "insider_trading": 60, "pledging": 70, "credit_rating": 38, "capex": 55, "dividend": 34,
    "bonus_split": 45, "order_win": 45, "press_release": 28, "earnings_call": 30,
    "investor_meetings": 8, "fund_use": 12, "postal_ballot": 14, "agm_egm": 14, "results_ad": 10, "unclassified": 4,
}

TOP_ROLE = re.compile(r"\b(MD|CEO|CFO|managing director|chief executive|chief financial|chairman|chairperson)\b", re.I)
MID_ROLE = re.compile(r"\b(executive director|whole[- ]time director|COO|chief operating|president)\b", re.I)
LOW_ROLE = re.compile(r"\b(independent director|company secretary|group head|head,|compliance officer|additional director)\b", re.I)
PERSON = [
    re.compile(r"(?:Mr|Ms|Mrs|Dr|Shri|Smt)\.?\s+([A-Z][\w'.]*(?:\s+[A-Z][\w'.]*){0,3})"),
    re.compile(r"\b([A-Z][\w'.]*(?:\s+[A-Z][\w'.]*){1,3})\s+(?:as|has been|was|is)\s+(?:the\s+)?(?:new\s+)?"
               r"(?:an?\s+)?(?:Director|MD|CEO|CFO|Chair|Executive|Independent|Managing|Whole)"),
]
NOT_PERSON = re.compile(r"\b(Bank|Ltd|Limited|Board|Shareholders|Company|Committee|RBI|SEBI|India)\b")
# a total amount must carry a unit; bare rupee figures are usually per-share prices
AMOUNT = re.compile(r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d+)?)\s*(crore|cr\b|lakh|bn|billion|mn|million)", re.I)
LT_SCALE = {"significant": (1000, 2500), "large": (2500, 5000), "major": (5000, 10000),
            "mega": (10000, 20000), "ultra-mega": (20000, 40000)}


def classify(title: str, desc: str = "") -> str:
    text = f"{title} || {desc}"
    # description often reveals what a generic subject hides (e.g. postal ballot approving a CEO)
    if re.search(r"postal ballot|outcome", title, re.I) and TOP_ROLE.search(desc) and re.search(r"approv|appoint", desc, re.I):
        return "management_change"
    if re.search(r"repayment of commercial paper|redeem", text, re.I):
        return "unclassified"
    if re.search(r"monitoring agency", text, re.I):
        return "fund_use"
    for cat, rx in COMPILED:
        if rx.search(text):
            return cat
    return "unclassified"


def person(text: str) -> str | None:
    for rx in PERSON:
        for m in rx.finditer(text):
            name = m.group(1).strip(" .")
            if not NOT_PERSON.search(name) and len(name.split()) >= 2:
                return name
    return None


def amount_cr(text: str) -> float | None:
    m = AMOUNT.search(text)
    if not m:
        return None
    v = float(m.group(1).replace(",", ""))
    unit = m.group(2).lower().strip()
    return v * {"crore": 1, "cr": 1, "lakh": 0.01, "bn": 100, "billion": 100, "mn": 0.1, "million": 0.1}[unit]


def score(item: dict, company: dict, care: list[str]) -> dict:
    """Returns {category, label, score, tier, why, facts} for one filing."""
    title, desc = item.get("title", ""), item.get("desc", "")
    text = f"{title}. {desc}"
    cat = classify(title, desc)
    s = BASE.get(cat, 10)
    why, facts = None, {}
    meta = company.get("meta", {})
    mcap = meta.get("mcap")
    ttm = company.get("ttm_sales")

    if cat == "management_change":
        who = person(desc) or person(title)
        facts["person"] = who
        if TOP_ROLE.search(text):
            s += 18
            facts["level"] = "top"
        elif MID_ROLE.search(text):
            s += 0
            facts["level"] = "mid"
        elif LOW_ROLE.search(text):
            s -= 30
            facts["level"] = "low"
        if re.search(r"re-?appoint", text, re.I):
            s -= 22
            facts["event"] = "reappointment"
        elif re.search(r"resign|cessation|superannuat|retire", text, re.I):
            facts["event"] = "exit"
            s += 4 if facts.get("level") == "top" else 0
        else:
            facts["event"] = "appointment"
        why = {"top": "Change at the very top. Background on the incoming person is below.",
               "mid": "Board-level change.", "low": "Below-board or independent-director change."}.get(facts.get("level"), "Leadership change.")
        if facts.get("event") == "reappointment":
            why = "Continuity: an existing executive was reappointed, so nothing changes."
        if facts.get("event") == "exit" and facts.get("level") == "low":
            why = "Planned retirement of a business head. Worth noting, not acting on."
    elif cat == "fund_raise":
        amt = amount_cr(text)
        if amt and mcap:
            pct = amt / mcap * 100
            facts.update(amount_cr=amt, pct_mcap=round(pct, 2))
            s += 10 if pct > 2 else 0
            why = f"₹{amt:,.0f} Cr ≈ {pct:.1f}% of market cap. Check dilution and what the money is for."
        else:
            why = "Fresh equity. Check the issue size, the price discount and the use of proceeds."
        if re.search(r"warrant|preferential", text, re.I) and re.search(r"promoter", text, re.I):
            why += " The promoter is subscribing, which signals confidence."
    elif cat == "order_win":
        amt = amount_cr(text)
        rng = next((v for k, v in LT_SCALE.items() if re.search(rf"\b{k}\b", text, re.I)), None)
        if amt is None and rng:
            amt = sum(rng) / 2
            facts["amount_band_cr"] = rng
        if amt and ttm:
            pct = amt / ttm * 100
            facts.update(amount_cr=amt, pct_ttm_rev=round(pct, 2))
            s += 25 if pct > 5 else 10 if pct > 2 else -10
            band = f"₹{rng[0]:,}–{rng[1]:,} Cr (company's own 'significant' band)" if rng else f"₹{amt:,.0f} Cr"
            why = f"{band} ≈ {pct:.1f}% of trailing revenue. " + ("Moves the needle." if pct > 5 else "Routine order flow at this scale.")
        if why is None:
            why = "The order value is not in the headline. Open the filing for size and duration."
    elif cat == "insider_trading":
        if re.search(r"promoter", text, re.I) and re.search(r"sold|sale|sell|dispos", text, re.I):
            s += 8
            why = "A promoter sold shares. Check the size against total promoter holding before reading anything into it."
        else:
            why = "Insider disclosure."
    elif cat == "litigation":
        amt = amount_cr(text)
        if re.search(r"allowed|set aside|in favou?r|stayed|quash", text, re.I):
            s -= 6
            why = "Legal update that went the company's way."
        elif re.search(r"CIRP|insolvency", text, re.I):
            why = "Insolvency-tribunal proceedings involving the company. Read the order to see which side it is on."
        elif re.search(r"penalt|fine|demand", text, re.I):
            why = "Regulatory penalty. Open the filing for the amount." if not amt else f"Penalty of about ₹{amt:,.0f} Cr."
        if amt and ttm and amt / ttm > 0.01:
            s += 12
    elif cat == "credit_rating":
        if re.search(r"reaffirm", text, re.I):
            s -= 18
            why = "Rating reaffirmed, no change."
        elif re.search(r"downgrad|negative watch|outlook.*negative", text, re.I):
            s += 30
            why = "Rating downgrade or negative watch. Borrowing costs could rise."
        elif re.search(r"upgrad", text, re.I):
            s += 8
            why = "Rating upgrade."
    elif cat == "M&A":
        if re.search(r"wholly[- ]owned|internal|step[- ]down|amalgamation of .*subsidiar", text, re.I) \
                and not re.search(r"share swap|acqui|external|third[- ]party", text, re.I):
            s -= 30
            why = "Internal reorganisation of wholly-owned subsidiaries. No outside party is involved."
        amt = amount_cr(text)
        if amt and mcap:
            facts.update(amount_cr=amt, pct_mcap=round(amt / mcap * 100, 2))
            why = f"Deal value ₹{amt:,.0f} Cr ≈ {amt / mcap * 100:.1f}% of market cap."
    elif cat == "press_release":
        if re.search(r"clarif|rumou?r|verification", text, re.I):
            s += 14
            why = "The exchange asked about a media report. Read the company's answer."
    elif cat == "earnings_call":
        why = "Transcript filed. The promises-vs-delivery view for this company can be refreshed."
    elif cat == "fund_use":
        why = ("Monitoring report on how earlier issue money was spent: no deviation." if re.search(r"no deviation", text, re.I)
               else "Monitoring report on use of issue proceeds. Check for any deviation.")
        if not re.search(r"no deviation", text, re.I):
            s += 40
    elif cat == "results_ad":
        why = "Newspaper ad for results that were already filed."
    elif cat == "investor_meetings":
        why = None
    elif cat == "unclassified" and llm.available() and not COMPILED[-1][1].search(text):
        guess = llm.call("extract", f"Classify this Indian exchange filing into one of {list(BASE)}. "
                                    f"Reply JSON {{\"category\":..}}.\n{text[:500]}")
        if guess and guess.get("category") in BASE:
            cat = guess["category"]
            s = BASE[cat]

    bucket = BUCKET.get(cat, cat)
    if bucket in care:
        s += 10
    s = max(0, min(100, s))
    tier = "act" if s >= 65 else "know" if s >= 35 else "routine"
    return {"category": cat, "bucket": bucket, "label": LABEL.get(cat, cat), "score": s,
            "tier": tier, "why": why, "facts": facts}
