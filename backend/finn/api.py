"""FastAPI surface. The frontend needs only /api/bundle; everything else is for live pull."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import engine, store
from .research import dossier

app = FastAPI(title="FINN", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
_BUNDLE: dict = {}


@app.get("/api/health")
def health():
    return {"ok": True, "as_of": engine.as_of().isoformat()}


@app.get("/api/bundle")
def bundle(refresh: bool = False):
    global _BUNDLE
    if refresh or not _BUNDLE:
        _BUNDLE = engine.bundle()
    return _BUNDLE


@app.get("/api/research/{symbol}")
def research(symbol: str):
    c = engine.company(symbol.upper())
    if not c or not c.get("quarters"):
        raise HTTPException(404, f"No primary data found for {symbol.upper()} (Screener lookup failed).")
    return dossier(c)


@app.get("/api/ask")
def ask(q: str):
    known = list((_BUNDLE or {}).get("research", {}).keys())
    p = engine.parse_ask(q, known)
    if not p["symbol"]:
        raise HTTPException(400, "Name a company or NSE ticker, e.g. 'DIXON promises vs delivery'.")
    return {**p, "dossier": research(p["symbol"])}


@app.get("/api/usage")
def usage():
    return store.llm_usage()


DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
