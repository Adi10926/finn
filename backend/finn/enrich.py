"""Push-side enrichment: who is the incoming person?

Order of preference: curated cache (data/people.json) -> grounded LLM search (Gemini +
Google Search, cached forever) -> None (UI shows 'search LinkedIn' deep link instead).
Secondary sources are fine here (the brief allows it for push enrichment); the pull-side
research engine never calls this.
"""
from __future__ import annotations

import json
from functools import lru_cache
from urllib.parse import quote_plus

from . import llm
from .config import DATA


@lru_cache(maxsize=1)
def _curated() -> dict:
    p = DATA / "people.json"
    return json.loads(p.read_text()) if p.exists() else {}


def bio(name: str | None, company: str = "") -> dict | None:
    if not name:
        return None
    hit = _curated().get(name.lower())
    if hit:
        return dict(hit, provenance="curated cache")
    if llm.available():
        res = llm.call("search", (
            f"Professional background of {name}, newly appointed at {company} (India). "
            "Return JSON: {name, previous (last role), career: [<=4 short lines], education, so_what "
            "(one sentence on why this hire matters to an investor), sources:[{title,url}]}. "
            "Use LinkedIn / company pages / reputable press. If unsure, say so."), grounded=True)
        if isinstance(res, dict) and res.get("name"):
            return dict(res, provenance="LLM + web search")
    return {"name": name, "provenance": "lookup link",
            "sources": [{"title": f"Search LinkedIn for {name}",
                         "url": f"https://www.linkedin.com/search/results/people/?keywords={quote_plus(name + ' ' + company)}"}]}
