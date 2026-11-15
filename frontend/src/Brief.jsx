import { useMemo, useState } from 'react'
import { WINDOWS, ago, inWindow, personalise } from './lib.js'
import { Bio, ResultsTable } from './ui.jsx'

function Row({ it, asOf, onOpenCompany }) {
  const [open, setOpen] = useState(false)
  const hasDetail = it.results || it.bio || it.related?.length || it.url
  return (
    <div className={`row ${it.tier}`}>
      <div className="margin">
        <div className="tick">{it.symbol}</div>
        <div className="when">{ago(it.date, asOf)}</div>
      </div>
      <button className="body" onClick={() => setOpen(o => !o)} aria-expanded={open}>
        <div className="kind">{it.label}</div>
        <p className="headline">{it.desc || it.title}</p>
        {it.why && <p className="why">{it.why}</p>}
        {!open && hasDetail && <div className="more">{it.results ? 'Show headline numbers' : it.bio ? `Who is ${it.bio.name}?` : 'Show filing'}{it.related?.length ? ` · ${it.related.length + 1} filings merged` : ''}</div>}
      </button>
      {open && (
        <div className="detail">
          {it.results && <><h4>First cut from the results filing ({it.results.basis})</h4><ResultsTable r={it.results} /></>}
          {it.bio && <><h4>Incoming</h4><Bio b={it.bio} /></>}
          {it.related?.length > 0 && <><h4>Same event, also filed</h4>{it.related.map((r, i) => <div key={i} className="why">{r.title} ({ago(r.date, asOf)})</div>)}</>}
          <h4>Source</h4>
          <a className="linkout" href={it.url} target="_blank" rel="noreferrer">{it.title}</a>
          <div style={{ marginTop: 12 }}><button className="linkout" onClick={() => onOpenCompany(it.symbol)}>Research {it.symbol}</button></div>
        </div>
      )}
    </div>
  )
}

export default function Brief({ data, care, onOpenCompany }) {
  const [hours, setHoursRaw] = useState(24)
  const [auto, setAuto] = useState(true)   // only auto-widen the default view, never a window the user picked
  const setHours = h => { setAuto(false); setHoursRaw(h) }
  const asOf = data.as_of
  const all = useMemo(() => data.feed.map(f => personalise(f, care)), [data, care])
  const pick = h => all.filter(i => inWindow(i, asOf, h))
  let items = pick(hours)
  let expandedTo = null
  // A quiet window shouldn't produce an empty screen: widen to the nearest window with something material.
  // Widen until something actually needs the investor (falls back to anything material).
  if (auto && !items.some(i => i.tier === 'act')) {
    const w = WINDOWS.find(w => w.h > hours && pick(w.h).some(i => i.tier === 'act'))
      || WINDOWS.find(w => w.h > hours && pick(w.h).some(i => i.tier !== 'routine'))
    if (w) { expandedTo = w; items = pick(w.h) }
  }
  const act = items.filter(i => i.tier === 'act').sort((a, b) => b.score - a.score)
  const know = items.filter(i => i.tier === 'know').sort((a, b) => b.score - a.score)
  const routine = items.filter(i => i.tier === 'routine')
  const groups = Object.entries(routine.reduce((g, i) => ((g[i.label] = g[i.label] || []).push(i), g), {})).sort((a, b) => b[1].length - a[1].length)
  const total = items.length || 1
  const firstWindowLabel = WINDOWS.find(w => w.h === hours)?.label.toLowerCase()

  return (
    <>
      <section className="budget" aria-label="Attention budget">
        <h1>
          <span className="n-act">{act.length} need{act.length === 1 ? 's' : ''} you.</span>{' '}
          <span className="n-know">{know.length} worth knowing.</span>{' '}
          <span className="n-rt">{routine.length} filed away.</span>
        </h1>
        <div className="tally" aria-hidden="true">
          <span style={{ flex: act.length, background: 'var(--red)' }} />
          <span style={{ flex: know.length, background: 'var(--saffron)' }} />
          <span style={{ flex: routine.length || (total === 1 ? 1 : 0), background: 'var(--rule)' }} />
        </div>
        <p>
          {expandedTo
            ? `A quiet ${new Date(asOf).getDay() % 6 === 0 ? 'weekend' : 'day'}: nothing in the ${firstWindowLabel} needs you, so FINN is showing ${expandedTo.h === 168 ? 'this week' : 'the last ' + expandedTo.label.toLowerCase()}.`
            : `${items.length} filings across your 15 holdings, ranked by how much each moves this particular company.`}
        </p>
      </section>
      <div className="windows" role="group" aria-label="Time window">
        {WINDOWS.map(w => <button key={w.h} className="pill" aria-pressed={(expandedTo ? expandedTo.h : hours) === w.h} onClick={() => setHours(w.h)}>{w.label}</button>)}
      </div>

      <div className="ledger">
        {act.length > 0 && <div className="sect"><span>Needs you</span><span>{act.length}</span></div>}
        {act.map(it => <Row key={it.symbol + it.url + it.date} it={it} asOf={asOf} onOpenCompany={onOpenCompany} />)}
        {know.length > 0 && <div className="sect"><span>Worth knowing</span><span>{know.length}</span></div>}
        {know.map(it => <Row key={it.symbol + it.url + it.date} it={it} asOf={asOf} onOpenCompany={onOpenCompany} />)}
        {act.length + know.length === 0 && <div className="empty">No material filings in this window. FINN keeps watching your 15 holdings and posts here when something lands.</div>}
      </div>

      {groups.length > 0 && <>
        <div className="sect"><span>Filed away</span><span>{routine.length}</span></div>
        <div className="routine">{groups.map(([label, xs]) => <RoutineGroup key={label} label={label} xs={xs} asOf={asOf} />)}</div>
      </>}
    </>
  )
}

function RoutineGroup({ label, xs, asOf }) {
  const [open, setOpen] = useState(false)
  const names = [...new Set(xs.map(x => x.symbol))]
  return (
    <>
      <button className="rgroup" onClick={() => setOpen(o => !o)} aria-expanded={open}>
        <span><b>{label}</b> ({xs.length})</span>
        <span>{names.slice(0, 3).join(', ')}{names.length > 3 ? ` +${names.length - 3}` : ''}</span>
      </button>
      {open && <div className="rlist">{xs.map((x, i) => <div key={i}><a href={x.url} target="_blank" rel="noreferrer">{x.symbol}</a>: {x.desc || x.title} ({ago(x.date, asOf)})</div>)}</div>}
    </>
  )
}
