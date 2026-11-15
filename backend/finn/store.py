"""Tiny SQLite key-value cache with TTL + an LLM usage ledger.

Every network fetch and every LLM call goes through here, so a re-run costs nothing.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager

from .config import CACHE

CACHE.mkdir(parents=True, exist_ok=True)
_DB = CACHE / "finn.sqlite"


@contextmanager
def _conn():
    c = sqlite3.connect(_DB)
    try:
        c.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT, ts REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS llm_usage (ts REAL, model TEXT, task TEXT, "
                  "in_tok INT, out_tok INT, cached INT)")
        yield c
        c.commit()
    finally:
        c.close()


def key(*parts) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:32]


def get(k: str, ttl: float | None = None):
    with _conn() as c:
        row = c.execute("SELECT v, ts FROM kv WHERE k=?", (k,)).fetchone()
    if not row:
        return None
    if ttl is not None and time.time() - row[1] > ttl:
        return None
    return json.loads(row[0])


def put(k: str, v) -> None:
    with _conn() as c:
        c.execute("REPLACE INTO kv VALUES (?,?,?)", (k, json.dumps(v), time.time()))


def log_llm(model: str, task: str, in_tok: int, out_tok: int, cached: bool) -> None:
    with _conn() as c:
        c.execute("INSERT INTO llm_usage VALUES (?,?,?,?,?,?)",
                  (time.time(), model, task, in_tok, out_tok, int(cached)))


def llm_usage() -> dict:
    with _conn() as c:
        rows = c.execute("SELECT model, task, SUM(in_tok), SUM(out_tok), COUNT(*), SUM(cached) "
                         "FROM llm_usage GROUP BY model, task").fetchall()
    return [dict(model=r[0], task=r[1], in_tok=r[2] or 0, out_tok=r[3] or 0,
                 calls=r[4], cache_hits=r[5] or 0) for r in rows]
