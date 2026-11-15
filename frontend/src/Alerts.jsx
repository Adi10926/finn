import { useMemo } from 'react'
import { CARE_LABELS, ago, daysBetween, eodAlerts, fmtPx, personalise } from './lib.js'
import { Spark } from './ui.jsx'

export default function Alerts({ data, rules, setRules, onOpenCompany }) {
  const { volMult, move, care } = rules
  const look = data.defaults.volume_lookback
  const asOf = data.as_of
  const eod = useMemo(() => data.portfolio.flatMap(p =>
    eodAlerts(p.series, volMult, look, move).map(a => ({ ...a, symbol: p.symbol, name: p.name, series: p.series }))
  ).sort((a, b) => b.date.localeCompare(a.date)), [data, volMult, move, look])
  const filings = data.feed.map(f => personalise(f, care))
    .filter(f => care.includes(f.bucket) && f.tier === 'act' && daysBetween(f.date, asOf) <= 7)
  const sim = data.portfolio.some(p => p.simulated)
  const toggle = c => setRules({ ...rules, care: care.includes(c) ? care.filter(x => x !== c) : [...care, c] })

  return (
    <>
      <div className="ph">
        <h2>You decide what's unusual</h2>
        <p>FINN checks every holding after the close against these rules and tells you only when one trips.</p>
      </div>
      <div className="rules">
        <div className="rule">
          <label htmlFor="vm">Volume spike <output>{volMult.toFixed(1)}×</output></label>
          <small>Day's volume vs its {look}-day average</small>
          <input id="vm" type="range" min="1.2" max="5" step="0.1" value={volMult} onChange={e => setRules({ ...rules, volMult: +e.target.value })} />
        </div>
        <div className="rule">
          <label htmlFor="mv">Price move <output>±{move.toFixed(1)}%</output></label>
          <small>Close-to-close, either direction</small>
          <input id="mv" type="range" min="1" max="10" step="0.5" value={move} onChange={e => setRules({ ...rules, move: +e.target.value })} />
        </div>
        <div className="rule">
          <label as="div">Filings I care about</label>
          <small>Alert the moment one of these is filed and FINN rates it as needing you</small>
          <div className="cats">
            {Object.entries(CARE_LABELS).map(([k, l]) => <button key={k} className="pill" aria-pressed={care.includes(k)} onClick={() => toggle(k)}>{l}</button>)}
          </div>
        </div>
      </div>
      {sim && <div className="warn">Prices in this build are simulated because market data could not be reached when the snapshot was made. Deploy with network access and FINN pulls end-of-day data from Yahoo Finance.</div>}

      <div className="sect" style={{ marginTop: 6 }}><span>Tripped in the last 5 sessions</span><span>{eod.length}</span></div>
      <div className="ledger">
        {eod.length === 0 && <div className="empty">Nothing crossed {volMult.toFixed(1)}× volume or ±{move}% this week. Loosen a rule above to see what's close.</div>}
        {eod.map((a, i) => (
          <div key={i} className={`row ${a.hits.length > 1 ? 'act' : 'know'}`}>
            <div className="margin"><div className="tick">{a.symbol}</div><div className="when">{ago(a.date, asOf)}</div></div>
            <button className="body" onClick={() => onOpenCompany(a.symbol)}>
              <div className="kind">{a.hits.map(h => h.rule === 'volume' ? 'Volume' : 'Price').join(' + ')}</div>
              <p className="headline">{a.hits.map(h => h.text).join(' · ')}</p>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 6 }}>
                <span className="why" style={{ margin: 0 }}>Closed {fmtPx(a.close)} ({a.mv > 0 ? '+' : ''}{a.mv.toFixed(1)}%)</span>
                <Spark values={a.series.slice(-30).map(d => d.close)} color={a.mv < 0 ? 'var(--red)' : 'var(--green)'} />
              </div>
            </button>
          </div>
        ))}
      </div>

      <div className="sect"><span>Filings that tripped your categories, this week</span><span>{filings.length}</span></div>
      <div className="ledger">
        {filings.length === 0 && <div className="empty">None this week in the categories you picked.</div>}
        {filings.map((f, i) => (
          <div key={i} className="row act">
            <div className="margin"><div className="tick">{f.symbol}</div><div className="when">{ago(f.date, asOf)}</div></div>
            <button className="body" onClick={() => onOpenCompany(f.symbol)}>
              <div className="kind">{f.label}</div>
              <p className="headline">{f.desc || f.title}</p>
              {f.why && <p className="why">{f.why}</p>}
            </button>
          </div>
        ))}
      </div>
    </>
  )
}
