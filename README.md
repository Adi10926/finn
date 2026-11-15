# FINN — a financial investment agent that edits your attention

Mobile-first PWA + Python backend. **Push** tells you what changed across a 15-stock NSE portfolio and why it matters for *that* company; **Pull** researches any NSE ticker from primary sources and checks what management promised against what the filed numbers show.

```
frontend/   React + Vite PWA (Brief · Alerts · Ask · Book). Works fully offline from snapshot.json
backend/    FastAPI + pipeline (sources → classify/score → results → alerts → research)
data/raw/   Screener snapshot of 16 companies (real filed numbers + exchange filings, Nov 2026)
data/ledgers.json  guidance ledger extracted from Dixon's Q2 FY27 concall (NSE filing)
data/people.json   curated bios for the two top-level management changes in the window
```

## Run it

```bash
# backend
pip install -r backend/requirements.txt
cd backend && uvicorn finn.api:app --port 8000          # live: NSE/BSE, Yahoo, Screener
# frontend
cd frontend && npm i && npx vite                         # http://localhost:5173 (proxies /api)

make snapshot          # run full pipeline against live sources, freeze to frontend/public/snapshot.json
make test              # 8 offline unit tests
docker build -t finn . && docker run -p 8000:8000 -e GEMINI_API_KEY=... finn
```
Render: `render.yaml` deploys the single container on the free plan. Without `GEMINI_API_KEY` everything still works: the LLM only adds language on top of deterministic output.

## How it works

**Push: the Brief.** Every filing is classified (17 categories, adapted from the reference taxonomy, plus `order_win`, `results_ad`, `fund_use`) and given a 0–100 *materiality* score. The scorer treats materiality as relative to the company. An order is divided by trailing revenue; L&T's own "significant" band works out to 0.6% of revenue, so it is routine. An issue is divided by market cap. A management change is weighed by who it is (CEO/MD/CFO/chair vs a reappointed executive vs a retiring business head). A rating reaffirmation is marked as no change. Filings describing one event are merged, such as the board approval plus the RBI approval, or the results plus the deck plus the shareholder letter. The headline is an attention budget: *"1 needs you. 2 worth knowing. 17 filed away."* If the chosen window is quiet (it's a Sunday), FINN widens to the nearest window with something that needs you and says so, rather than showing an empty screen.

- **Results:** a first cut of Revenue / EBITDA / PBT / PAT, QoQ and YoY, plus quality flags (margin bps change, other income as a share of PBT, revenue up but PAT down). For banks EBITDA is shown as *not meaningful* instead of a misleading number.
- **Management change:** a bio of the incoming person (curated cache → Gemini with Google Search grounding → LinkedIn search link). Push-side enrichment is the only place secondary sources are used.
- **Alerts:** volume ≥ k× the 20-day average and |move| ≥ x%, plus filings in categories you pick. Thresholds are sliders and are recomputed on-device, so they respond instantly and work offline.

**Pull: Ask.** Type or speak (Web Speech API, en-IN): "Dixon promises vs delivery", "Asian Paints cash quality". The research engine uses **only** filed financials and concall transcripts:
- Snapshot, numbers (TTM + latest quarter), trajectory (3y/5y CAGR, margin path), balance sheet (D/E, working-capital cycle, CWIP), cash quality (CFO/PAT per year and 5-year cumulative, FCF).
- **Promises**: guidance extracted from the latest transcript, then tested *deterministically* against filed numbers: run-rate tests, capex versus gross-block history, margin path versus guided bps, and stated tone versus reported PAT. Ambiguous guidance is flagged as unresolved, not guessed.
- Bull / bear assembled from those facts, each with its source. With a key, a model may rewrite the points but is instructed to use only the facts passed in.

## Model routing and cost
| Step | How | Cost |
|---|---|---|
| Classify + score ~95% of filings | regex taxonomy + arithmetic | ₹0 |
| QoQ/YoY, ratios, alerts, promise tests | Python | ₹0 |
| Unmatched filing (rare) | `gemini-2.5-flash-lite` | ~0 |
| Guidance from transcript | flash-lite over **forward-looking chunks only** (keyword filter drops ~70% of tokens) | fractions of a cent per call |
| Bull/bear rewrite | `gemini-2.5-flash`, facts-only prompt | cents |
| Incoming-exec bio | flash + Google Search grounding, cached forever | cents, once per person |

Every fetch and LLM call goes through a SQLite cache (`store.py`). Usage is logged and returned in the bundle. Groq (llama-3.1-8b / 3.3-70b) is a drop-in alternative via `GROQ_API_KEY`.

## Honest status (read this before deploying)
- The build sandbox could not reach Yahoo, NSE, BSE or Screener directly. The snapshot in `data/raw/` was collected through a web reader from Screener's public pages (real filed numbers and real exchange filings as of 13–15 Nov 2026). Spot-check a few numbers against Screener before relying on them.
- **EOD prices in the shipped snapshot are simulated** (a seeded random walk anchored to the real last close), and the UI says so in two places. Run `make snapshot` on a machine with internet and they are replaced by Yahoo data.
- The live adapters (`sources/announcements.py` NSE API with cookie warm-up, `sources/screener.py` HTML parser, `sources/prices.py` yfinance) are written to those sites' public formats but **could not be exercised from the sandbox**. Run `make snapshot` once locally to confirm, and fix selectors if a site has changed.
- The LLM path is implemented but was not exercised without a key. The Dixon ledger and the two bios are cached one-time extractions, each with its source link.
