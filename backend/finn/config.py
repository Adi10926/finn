"""FINN configuration: portfolio, research set, default thresholds, model routing.

Everything an investor would tune lives here or is overridable per request.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"            # Screener snapshot (seed) in a tiny section-CSV format
CACHE = DATA / "cache"        # SQLite cache (LLM calls, fetched docs, prices)
SNAPSHOT = ROOT / "frontend" / "public" / "snapshot.json"

# --- Portfolio: 15 NSE names across sizes & sectors ---------------------------------
PORTFOLIO: dict[str, dict] = {
    "RELIANCE":   {"qty": 120, "sector": "Energy / Conglomerate"},
    "HDFCBANK":   {"qty": 400, "sector": "Private Bank"},
    "BAJFINANCE": {"qty": 150, "sector": "NBFC"},
    "TCS":        {"qty": 60,  "sector": "IT Services"},
    "INFY":       {"qty": 140, "sector": "IT Services"},
    "KPITTECH":   {"qty": 220, "sector": "Auto Software"},
    "BHARTIARTL": {"qty": 80,  "sector": "Telecom"},
    "LT":         {"qty": 40,  "sector": "Engineering & Construction"},
    "ITC":        {"qty": 600, "sector": "FMCG / Tobacco"},
    "SUNPHARMA":  {"qty": 90,  "sector": "Pharma"},
    "TITAN":      {"qty": 35,  "sector": "Jewellery & Lifestyle"},
    "TRENT":      {"qty": 50,  "sector": "Retail"},
    "ETERNAL":    {"qty": 450, "sector": "Food delivery / Quick commerce"},
    "DIXON":      {"qty": 12,  "sector": "Electronics manufacturing"},
    "POLYCAB":    {"qty": 20,  "sector": "Cables & Wires"},
}
# Ad-hoc research demo set (ASIANPAINT is deliberately outside the portfolio)
RESEARCH_SET = ["DIXON", "ASIANPAINT", "TCS", "POLYCAB"]

# --- Push defaults (all user-overridable from the app) --------------------------------
DEFAULTS = {
    "window_hours": 24,
    "volume_multiple": 2.0,      # today's volume vs 20-day average
    "volume_lookback": 20,
    "price_move_pct": 4.0,       # |close-to-close| move
    "care_categories": ["results", "M&A", "fund_raise", "management_change",
                        "litigation", "insider_trading", "pledging", "credit_rating"],
}

# --- Model routing ---------------------------------------------------------------------
# Deterministic code does the bulk: classification, scoring, QoQ/YoY, ratios, alerts.
# LLMs only where language is the job. Cheapest model that can do each step.
MODELS = {
    "extract": os.getenv("FINN_MODEL_EXTRACT", "gemini-2.5-flash-lite"),  # bulk: transcript chunks -> JSON
    "reason":  os.getenv("FINN_MODEL_REASON",  "gemini-2.5-flash"),       # narrative vs numbers, bull/bear
    "search":  os.getenv("FINN_MODEL_SEARCH",  "gemini-2.5-flash"),       # grounded bio lookup (push enrichment)
    "groq_extract": os.getenv("FINN_GROQ_EXTRACT", "llama-3.1-8b-instant"),
    "groq_reason":  os.getenv("FINN_GROQ_REASON",  "llama-3.3-70b-versatile"),
}
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_KEY = os.getenv("GROQ_API_KEY", "")

# Live mode = try exchange/Yahoo/Screener; snapshot mode = use data/raw only.
LIVE = os.getenv("FINN_LIVE", "1") == "1"
AS_OF = os.getenv("FINN_AS_OF", "")  # override "now" for demos, e.g. 2026-11-15

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
