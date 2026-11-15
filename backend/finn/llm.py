"""LLM router: pick the cheapest capable model per task, cache every call.

Tasks
  extract  -> flash-lite / llama-8b : chunk-level JSON extraction from transcripts, filings
  reason   -> flash / llama-70b     : narrative-vs-numbers verdicts, bull/bear prose
  search   -> flash + Google grounding : push-side bios for management changes

If no key is configured, every call returns None and callers fall back to deterministic
output. The app is fully usable with zero LLM spend; models only add language on top.
"""
from __future__ import annotations

import json
import re

import httpx

from . import store
from .config import GEMINI_KEY, GROQ_KEY, MODELS

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k}"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def available() -> bool:
    return bool(GEMINI_KEY or GROQ_KEY)


def _json_from(text: str):
    m = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    body = m.group(1) if m else text
    try:
        return json.loads(body)
    except Exception:
        m = re.search(r"(\{.*\}|\[.*\])", body, re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                return None
    return None


def call(task: str, prompt: str, system: str = "", as_json: bool = True,
         grounded: bool = False, max_tokens: int = 1200):
    """Return parsed JSON (or text). Cached forever on (task, model, prompt)."""
    if not available():
        return None
    model = MODELS[task] if GEMINI_KEY else MODELS["groq_" + ("reason" if task != "extract" else "extract")]
    k = store.key("llm", model, task, system, prompt, grounded)
    hit = store.get(k)
    if hit is not None:
        store.log_llm(model, task, 0, 0, True)
        return hit
    try:
        if GEMINI_KEY:
            body = {
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": max_tokens},
            }
            if system:
                body["systemInstruction"] = {"parts": [{"text": system}]}
            if as_json and not grounded:
                body["generationConfig"]["responseMimeType"] = "application/json"
            if grounded:
                body["tools"] = [{"google_search": {}}]
            r = httpx.post(GEMINI_URL.format(m=model, k=GEMINI_KEY), json=body, timeout=60)
            r.raise_for_status()
            data = r.json()
            text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
            u = data.get("usageMetadata", {})
            store.log_llm(model, task, u.get("promptTokenCount", 0), u.get("candidatesTokenCount", 0), False)
        else:
            msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
            body = {"model": model, "messages": msgs, "temperature": 0.1, "max_tokens": max_tokens}
            if as_json:
                body["response_format"] = {"type": "json_object"}
            r = httpx.post(GROQ_URL, json=body, headers={"Authorization": f"Bearer {GROQ_KEY}"}, timeout=60)
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"]
            u = data.get("usage", {})
            store.log_llm(model, task, u.get("prompt_tokens", 0), u.get("completion_tokens", 0), False)
    except Exception as e:  # network/quota: degrade gracefully
        print(f"[llm] {task} failed: {e}")
        return None
    out = _json_from(text) if as_json else text.strip()
    if out is not None:
        store.put(k, out)
    return out
