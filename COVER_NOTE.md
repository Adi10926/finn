**To:** assessment@enam.com
**Subject:** IIT Delhi – AI Engineer - 2027

Hello,

Please find my submission for the FINN build challenge.

- Prototype (open on a phone): <DEPLOYED LINK>
- Repository: <GITHUB LINK>
- AI build history: <SHARE LINK(S)>

**What I built.** FINN treats an investor's attention as the scarce resource. The home screen opens with an attention budget ("1 needs you. 2 worth knowing. 17 filed away."), not a feed. Below it is a ledger of filings across a 15-stock portfolio, ranked by how much each one moves that particular company. There are four surfaces: **Brief** (windowed digest), **Alerts** (user-set volume, price and filing-category rules), **Ask** (typed or voice research on any NSE ticker) and **Book** (holdings with day move, volume multiple and last-quarter YoY).

**Key decisions**
1. *Materiality is relative, and it is arithmetic.* An order win is divided by trailing revenue, a fund raise by market cap, and a management change is weighed by role (CEO vs reappointed director vs retiring business head). This is why an L&T "significant" order is filed away (0.6% of revenue), while the Bajaj Finance QIP and promoter-warrant issue and the HDFC Bank CEO change rise to the top.
2. *Numbers first, language last.* About 95% of the pipeline (classification, scoring, QoQ/YoY, ratios, alerts and the promise checks) is deterministic and costs nothing. LLMs are used only where language is the job: transcript guidance extraction (flash-lite over keyword-filtered chunks, which drops ~70% of tokens), a facts-only bull/bear rewrite, and grounded bios. Everything is cached. With no API key the app is still fully usable.
3. *Analyse management, don't summarise them.* The Promises tab tests guidance against filed numbers. For Dixon Q2 FY27, IT-hardware run-rate is ahead of the ₹6,000 Cr guide. But the guided +80–100 bps margin uplift is unproven, because quarterly EBITDA margin is down 104 bps YoY. Management's own explanation (growth from memory-cost pass-through) agrees with the numbers, which is the problem: revenue is up 47% but EBITDA only 6%. An ambiguous volume guide (FY or H2?) is flagged rather than guessed.
4. *Pull uses only primary data.* Filed statements and transcripts. Secondary sources appear only in push-side bios, as the brief allows.
5. *The demo never breaks.* The same JSON bundle comes from the live API or from a frozen snapshot, so the phone link works without a backend.

**Deliberately left out:** intraday data, portfolio P&L accounting, user accounts and push notifications (the Alerts badge stands in for them), annual-report segment parsing (the hook exists, behind the model key), and broad LLM chat. A free-form chatbot over filings would have been the obvious build. A ranked, explainable ledger is faster to read.

**Caveats, stated plainly:** my build sandbox had no direct access to Yahoo, NSE or Screener. The shipped snapshot uses real filed numbers and filings collected through a web reader, but its EOD prices are simulated, and the app labels them as simulated. The live adapters are implemented for those sites but were validated only offline. The README lists exactly what to run to switch to live data.

**Next:** a promise ledger that carries across quarters (each call's guidance becomes the next quarter's test), web-push alerts, segment and auditor-note extraction from annual reports, related-party and contingent-liability deltas, and peer-relative materiality.

Thank you,
Aditya Kumar, IIT Delhi (2023CE11069)
