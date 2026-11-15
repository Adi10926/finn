import { useEffect, useRef, useState } from 'react'
import { fmtCr, fmtN, liveResearch, parseAsk, pct } from './lib.js'
import { Bars, Icon, ResultsTable } from './ui.jsx'

const TABS = [
  ['guidance', 'Promises'], ['numbers', 'Numbers'], ['trajectory', 'Trajectory'],
  ['balance', 'Balance sheet'], ['cash', 'Cash'], ['bullbear', 'Bull / bear'], ['about', 'Business'],
]

function Lines({ lines }) {
  return (lines || []).map((l, i) => <div key={i} className="line"><span className={`dot ${l.tone}`} /><span>{l.text}</span></div>)
}

function Promises({ g }) {
  if (!g?.available) return (
    <div className="pane">
      <p className="verdict">No promise ledger for this company yet.</p>
      <p className="why">{g?.note}</p>
      {g?.transcripts?.map((t, i) => <div key={i} className="line"><a className="linkout" href={t.url} target="_blank" rel="noreferrer">Concall transcript, {t.label}</a></div>)}
    </div>
  )
  const bad = g.checks.filter(c => c.tone === 'bad').length
  return (
    <div className="pane">
      <p className="verdict">{bad ? `${bad} of ${g.checks.length} checks find the story running ahead of the numbers.` : 'The filed numbers back up what management is saying.'}</p>
      <div className="src">Tested against the filed results. Call tone: {g.tone}.</div>
      {g.checks.map((c, i) => (
        <div key={i} className="promise">
          <div className="p">{c.promise}</div>
          <div className="t">{c.test}</div>
          <span className={`vtag ${c.tone}`}>{c.verdict}</span>
        </div>
      ))}
      <h4 style={{ margin: '20px 0 4px', fontSize: 15 }}>Open promises to check next quarter</h4>
      {g.guidance.filter(x => !x.check).map((x, i) => (
        <div key={i} className="open">{x.statement}<em>{x.period} · {x.speaker}</em>{x.flag && <div className="amb">{x.flag}</div>}</div>
      ))}
      <h4 style={{ margin: '20px 0 4px', fontSize: 15 }}>What analysts pushed on</h4>
      {g.analyst_pushback.map((x, i) => <div key={i} className="open">{x}</div>)}
      <div className="src" style={{ marginTop: 14 }}>Source: <a href={g.source.url} target="_blank" rel="noreferrer">{g.source.title}</a></div>
    </div>
  )
}

function Dossier({ d, tab, setTab }) {
  const s = d.snapshot, f = d.financials, tr = d.trajectory, bs = d.balance, cs = d.cash, bb = d.bullbear
  return (
    <div className="dossier">
      <div className="dhead">
        <h2>{s.name}</h2>
        <div className="sub">{d.symbol} · {s.sector}{d.source === 'screener-live' ? ' · fetched live' : ''}</div>
      </div>
      <div className="kpis">
        <div><b>{s.mcap ? fmtCr(s.mcap) : '—'}</b><span>Mkt cap</span></div>
        <div><b>{s.pe ? s.pe.toFixed(1) + '×' : '—'}</b><span>P/E</span></div>
        <div><b>{s.roce ? s.roce.toFixed(0) + '%' : '—'}</b><span>{s.kind === 'bank' ? 'ROA-ish ROCE' : 'ROCE'}</span></div>
        <div><b>{s.roe ? s.roe.toFixed(0) + '%' : '—'}</b><span>ROE</span></div>
      </div>
      <div className="dtabs" role="tablist">
        {TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{l}{k === 'guidance' && d.guidance?.available ? ' •' : ''}</button>)}
      </div>

      {tab === 'guidance' && <Promises g={d.guidance} />}
      {tab === 'numbers' && <div className="pane">
        {f.ttm && <p className="verdict">Trailing 12 months: revenue {fmtCr(f.ttm.revenue)}, PAT {fmtCr(f.ttm.pat)}{f.ttm.ebitda_margin ? `, EBITDA margin ${f.ttm.ebitda_margin}%` : ''}.</p>}
        {f.latest ? <ResultsTable r={f.latest} /> : <p className="why">Quarterly table not in this snapshot. FINN loads it on a live refresh.</p>}
        {f.latest?.spark?.sales && <><div className="src">Quarterly revenue, ₹ Cr</div><Bars labels={f.latest.periods.map(p => p.replace(/ 20/, " '"))} values={f.latest.spark.sales} /></>}
        <div className="src">{f.src}</div>
      </div>}
      {tab === 'trajectory' && (tr ? <div className="pane">
        <p className="verdict">{tr.verdict}.</p>
        <Lines lines={tr.lines} />
        <div className="src">Revenue (bars) and EBITDA margin (line), fiscal years</div>
        <Bars labels={tr.periods} values={tr.sales} line={tr.opm} />
        <div className="src">PAT, ₹ Cr</div>
        <Bars labels={tr.periods} values={tr.pat} />
        <div className="src">{tr.src}</div>
      </div> : <Missing />)}
      {tab === 'balance' && (bs ? <div className="pane">
        <Lines lines={bs.lines} />
        {bs.de && <><div className="src">Debt / equity, ×</div><Bars labels={bs.periods} values={bs.de} fmt={v => v.toFixed(2)} /></>}
        {bs.wc?.ccc && <><div className="src">Cash conversion cycle, days</div><Bars labels={bs.wc.periods} values={bs.wc.ccc} /></>}
        <div className="src">{bs.src}</div>
      </div> : <Missing />)}
      {tab === 'cash' && (cs ? <div className="pane">
        <Lines lines={cs.lines} />
        {cs.cfo_pat && <><div className="src">Cash from operations ÷ PAT, ×</div><Bars labels={cs.periods} values={cs.cfo_pat} fmt={v => v.toFixed(2)} /></>}
        {cs.fcf && <><div className="src">Free cash flow, ₹ Cr</div><Bars labels={cs.periods} values={cs.fcf} /></>}
        <div className="src">{cs.src}</div>
      </div> : <Missing />)}
      {tab === 'bullbear' && <div className="pane">
        <div className="case bull"><h3>Bull</h3>{(bb.bull_prose || bb.bull.map(b => b.text)).map((t, i) => <div key={i} className="line"><span className="dot good" />{t}</div>)}</div>
        <div className="case bear"><h3>Bear</h3>{(bb.bear_prose || bb.bear.map(b => b.text)).map((t, i) => <div key={i} className="line"><span className="dot bad" />{t}</div>)}</div>
        <div className="src">Every point comes from the filed numbers or the concall ({bb.method}). No news or broker notes are used.</div>
      </div>}
      {tab === 'about' && <div className="pane">
        <p className="verdict">{s.about}</p>
        <p className="why">{s.segments_note}</p>
        <div className="src">{s.src}</div>
      </div>}
    </div>
  )
}

const Missing = () => <div className="pane"><p className="why">This section needs the annual statements, which load when FINN refreshes from Screener live.</p></div>

export default function Ask({ data, focus, clearFocus }) {
  const [q, setQ] = useState('')
  const [res, setRes] = useState(null)
  const [tab, setTab] = useState('guidance')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [listening, setListening] = useState(false)
  const recRef = useRef(null)

  async function run(text) {
    const { sym, intent } = parseAsk(text, data.research)
    setErr('')
    if (!sym) { setErr('Name a company or NSE ticker, for example "Dixon promises vs delivery".'); return }
    let d = data.research[sym]
    if (!d) {
      if (!data.live) { setErr(`${sym} isn't in this offline snapshot. Connected to the backend, FINN researches any NSE ticker on Screener's coverage.`); return }
      setBusy(true)
      try { d = await liveResearch(sym) } catch (e) { setErr(e.message); setBusy(false); return }
      setBusy(false)
    }
    setRes(d)
    setTab(intent === 'numbers' ? 'numbers' : intent === 'guidance' && !d.guidance?.available ? 'numbers' : intent)
    window.scrollTo({ top: 0 })
  }

  useEffect(() => { if (focus) { setQ(focus); run(focus); clearFocus() } }, [focus])

  function voice() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { setErr('Voice input needs Chrome or Safari on a phone.'); return }
    if (listening) { recRef.current?.stop(); return }
    const r = new SR(); r.lang = 'en-IN'; r.interimResults = false
    r.onresult = e => { const t = e.results[0][0].transcript; setQ(t); run(t) }
    r.onend = () => setListening(false)
    recRef.current = r; setListening(true); r.start()
  }

  const chips = ['Dixon: promises vs delivery', 'Asian Paints cash quality', 'TCS bull vs bear', 'Polycab balance sheet', 'HDFC Bank numbers']
  return (
    <>
      <div className="composer">
        <form className="qbox" onSubmit={e => { e.preventDefault(); run(q) }}>
          <input value={q} onChange={e => setQ(e.target.value)} placeholder="Ask about any NSE company" aria-label="Ask FINN" />
          <button type="button" className={`iconbtn ghost ${listening ? 'live' : ''}`} onClick={voice} aria-label="Speak">{Icon.mic}</button>
          <button className="iconbtn" aria-label="Ask">{Icon.go}</button>
        </form>
        <div className="suggest">{chips.map(c => <button key={c} className="pill" onClick={() => { setQ(c); run(c) }}>{c}</button>)}</div>
      </div>
      {busy && <div className="empty">Reading the filings for this company…</div>}
      {err && <div className="empty">{err}</div>}
      {res ? <Dossier d={res} tab={tab} setTab={setTab} /> : !err && (
        <div className="ph">
          <h2>Research from primary sources</h2>
          <p>FINN answers from filed results, annual-report statements and concall transcripts, never from news or broker notes. Ask what management promised and whether the numbers delivered it.</p>
        </div>
      )}
    </>
  )
}
