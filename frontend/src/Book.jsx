import { fmtPx, pct, tone } from './lib.js'
import { Spark } from './ui.jsx'

export default function Book({ data, onOpenCompany }) {
  const rows = data.portfolio
  const value = rows.reduce((a, r) => a + r.value, 0)
  const dayPnl = rows.reduce((a, r) => a + r.value * (r.chg_pct / (100 + r.chg_pct)), 0)
  return (
    <>
      <div className="ph">
        <h2>Book</h2>
        <p>Fifteen holdings. Each row shows the day's move, how heavy the trading was, and how the last quarter landed.</p>
      </div>
      <div className="totals">
        <span>Value<br /><b>₹{(value / 1e5).toFixed(2)} L</b></span>
        <span style={{ textAlign: 'right' }}>Day<br /><b className={tone(dayPnl)}>{dayPnl >= 0 ? '+' : '−'}₹{Math.abs(Math.round(dayPnl)).toLocaleString('en-IN')}</b></span>
      </div>
      <div className="ledger">
        {rows.map(r => {
          const m = r.results?.metrics || []
          const rev = m.find(x => x.key === 'sales'), pat = m.find(x => x.key === 'pat')
          return (
            <button key={r.symbol} className="hold" onClick={() => onOpenCompany(r.symbol)}>
              <div><div className="nm">{r.symbol}</div><div className="sub">{r.sector} · {r.qty} sh</div></div>
              <div><div className="px">{fmtPx(r.price)}</div><div className={`chg ${tone(r.chg_pct)}`}>{pct(r.chg_pct)}</div></div>
              <div className="rs">
                <Spark values={r.series.slice(-30).map(d => d.close)} w={70} h={18} color={r.chg_pct < 0 ? 'var(--red)' : 'var(--green)'} />
                <span>Vol {r.vol_mult?.toFixed(1)}×</span>
                {r.results ? <span>{r.results.quarter}: rev <b className={tone(rev?.yoy)}>{pct(rev?.yoy, 0)}</b> · PAT <b className={tone(pat?.yoy)}>{pct(pat?.yoy, 0)}</b> YoY</span> : <span>Quarterlies load on live refresh</span>}
              </div>
            </button>
          )
        })}
      </div>
    </>
  )
}
