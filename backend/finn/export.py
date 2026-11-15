"""Run the whole pipeline once and freeze the output to frontend/public/snapshot.json.

The static build then works with no backend at all (phone demo never breaks), and the
live build uses the same JSON shape from /api/bundle.

    python -m finn.export            # live sources where reachable
    FINN_LIVE=0 python -m finn.export  # snapshot only
"""
from __future__ import annotations

import json

from . import engine
from .config import SNAPSHOT


def main():
    b = engine.bundle()
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(b, separators=(",", ":"), default=str))
    print(f"wrote {SNAPSHOT} · {len(b['feed'])} filings · {len(b['research'])} dossiers · "
          f"{SNAPSHOT.stat().st_size / 1024:.0f} KB · modes {b['data_modes']}")


if __name__ == "__main__":
    main()
