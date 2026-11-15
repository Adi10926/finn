"""Primary documents (concall transcripts, results PDFs): download, text, smart chunking.

Efficiency: we never send a whole 40-page transcript to a model. We split into ~1.5k-token
chunks and keep only chunks that contain forward-looking language or headline numbers.
On typical transcripts this cuts input tokens by ~65-75%.
"""
from __future__ import annotations

import io
import re

import httpx

from .. import store
from ..config import USER_AGENT

FORWARD = re.compile(
    r"\b(guid|expect|outlook|target|aim|aspire|should be|will be|going forward|next year|"
    r"FY ?2[6-9]|FY ?3\d|H2|second half|run[- ]rate|margin|capex|capacity|double[- ]digit|"
    r"bps|basis points|growth of|grow (at|by)|crore|million units)\b", re.I)


def pdf_text(url: str) -> str | None:
    k = store.key("pdf", url)
    hit = store.get(k)
    if hit is not None:
        return hit
    try:
        h = {"User-Agent": USER_AGENT, "Referer": "https://www.bseindia.com/"}
        r = httpx.get(url, headers=h, timeout=40, follow_redirects=True)
        r.raise_for_status()
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(r.content))
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception as e:
        print(f"[docs] {url}: {e}")
        return None
    store.put(k, text)
    return text


def chunks(text: str, size: int = 6000, overlap: int = 400) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text)
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + size])
        i += size - overlap
    return out


def forward_looking(text: str, min_hits: int = 3) -> list[str]:
    """Keep only chunks dense with forward-looking language / numbers."""
    return [c for c in chunks(text) if len(FORWARD.findall(c)) >= min_hits]
