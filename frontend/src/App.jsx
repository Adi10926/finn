import { useEffect, useMemo, useState } from 'react'
import Alerts from './Alerts.jsx'
import Ask from './Ask.jsx'
import Book from './Book.jsx'
import Brief from './Brief.jsx'
import { DEFAULT_CARE, daysBetween, eodAlerts, loadBundle, personalise, store } from './lib.js'
import { Icon } from './ui.jsx'

export default function App() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')
  const [tab, setTab] = useState(() => store.get('tab', 'brief'))
  const [focus, setFocus] = useState(null)
  const [rules, setRulesState] = useState(() => store.get('rules', { volMult: 2, move: 4, care: DEFAULT_CARE }))
  const setRules = r => { setRulesState(r); store.set('rules', r) }
  useEffect(() => { loadBundle().then(setData).catch(e => setErr(String(e))) }, [])
  useEffect(() => { store.set('tab', tab) }, [tab])

  const badge = useMemo(() => {
    if (!data) return 0
    const eod = data.portfolio.reduce((a, p) => a + eodAlerts(p.series, rules.volMult, data.defaults.volume_lookback, rules.move, 1).length, 0)
    const f = data.feed.map(x => personalise(x, rules.care)).filter(x => rules.care.includes(x.bucket) && x.tier === 'act' && daysBetween(x.date, data.as_of) <= 1).length
    return eod + f
  }, [data, rules])

  if (err) return <div className="app"><div className="empty">FINN couldn't load data: {err}. Reload to try again.</div></div>
  if (!data) return <div className="app"><div className="mast"><div className="mark"><i />FINN</div></div><div className="empty">Reading the overnight filings…</div></div>

  const open = sym => { setFocus(sym); setTab('ask') }
  const asOf = new Date(data.as_of).toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })
  return (
    <div className="app">
      <header className="mast">
        <div className="mark"><i />FINN</div>
        <div className="asof">As of <b>{asOf}</b><br /><span className="modechip">{data.live ? 'Live backend' : 'Offline snapshot'}{data.data_modes.prices === 'simulated' ? ' · simulated prices' : ''}</span></div>
      </header>
      <main>
        {tab === 'brief' && <Brief data={data} care={rules.care} onOpenCompany={open} />}
        {tab === 'alerts' && <Alerts data={data} rules={rules} setRules={setRules} onOpenCompany={open} />}
        {tab === 'ask' && <Ask data={data} focus={focus} clearFocus={() => setFocus(null)} />}
        {tab === 'book' && <Book data={data} onOpenCompany={open} />}
      </main>
      <footer className="foot">Filings: NSE/BSE. Fundamentals: Screener (company filings). Data as of {data.as_of}. Not investment advice.</footer>
      <div className="tabs">
        <nav aria-label="Sections">
          {[['brief', 'Brief'], ['alerts', 'Alerts'], ['ask', 'Ask'], ['book', 'Book']].map(([k, l]) => (
            <button key={k} aria-current={tab === k ? 'page' : undefined} onClick={() => setTab(k)}>
              {Icon[k === 'alerts' ? 'alert' : k]}{l}
              {k === 'alerts' && badge > 0 && <span className="badge">{badge}</span>}
            </button>
          ))}
        </nav>
      </div>
    </div>
  )
}
