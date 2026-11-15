import { fmtN, pct, tone } from './lib.js'

export function Spark({ values, w = 120, h = 30, color = 'var(--ink)' }) {
  const v = (values || []).filter(x => x != null)
  if (v.length < 2) return null
  const lo = Math.min(...v), hi = Math.max(...v), r = hi - lo || 1
  const pts = v.map((x, i) => `${(i / (v.length - 1)) * w},${h - 2 - ((x - lo) / r) * (h - 4)}`).join(' ')
  return <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true"><polyline points={pts} fill="none" stroke={color} strokeWidth="1.6" /></svg>
}

// Bars with labels: used for multi-year series in research.
export function Bars({ labels, values, fmt = fmtN, w = 340, h = 120, neg = false, line }) {
  const v = values.map(x => x ?? 0)
  const hi = Math.max(...v, 0), lo = Math.min(...v, 0), r = hi - lo || 1
  const bw = w / v.length
  const y0 = 14 + ((hi) / r) * (h - 34)
  const yy = x => 14 + ((hi - x) / r) * (h - 34)
  return (
    <svg className="chart" width="100%" viewBox={`0 0 ${w} ${h}`} role="img" aria-label="chart">
      <line x1="0" x2={w} y1={y0} y2={y0} stroke="var(--rule)" />
      {v.map((x, i) => (
        <g key={i}>
          <rect x={i * bw + bw * 0.18} width={bw * 0.64} y={Math.min(yy(x), y0)} height={Math.max(1, Math.abs(yy(x) - y0))}
            fill={x < 0 ? 'var(--red)' : i === v.length - 1 ? 'var(--ink)' : '#9AAAB5'} />
          {(i === v.length - 1 || i === 0) && <text x={i * bw + bw / 2} y={Math.min(yy(x), y0) - 3} textAnchor="middle" style={{ fill: 'var(--ink)', fontWeight: 600 }}>{fmt(x)}</text>}
          <text x={i * bw + bw / 2} y={h - 4} textAnchor="middle">{String(labels[i] || '').replace(/^Mar /, "'").replace(/^20/, "'")}</text>
        </g>
      ))}
      {line && (() => {
        const lv = line.filter(x => x != null); if (lv.length < 2) return null
        const lh = Math.max(...lv), ll = Math.min(...lv), lr = lh - ll || 1
        const pts = line.map((x, i) => x == null ? null : `${i * bw + bw / 2},${14 + ((lh - x) / lr) * (h - 50)}`).filter(Boolean).join(' ')
        return <polyline points={pts} fill="none" stroke="var(--saffron)" strokeWidth="2" />
      })()}
    </svg>
  )
}

export function ResultsTable({ r }) {
  if (!r) return null
  return (
    <>
      <table className="res">
        <thead><tr><th>{r.quarter} · ₹ Cr</th><th>Now</th><th>QoQ</th><th>YoY</th></tr></thead>
        <tbody>
          {r.metrics.map(m => (
            <tr key={m.key}>
              <td>{m.label}</td>
              {m.na ? <td colSpan="3" className="na">{m.na}</td> : <>
                <td>{fmtN(m.cur)}</td>
                <td className={tone(m.qoq)}>{pct(m.qoq, 0)}</td>
                <td className={tone(m.yoy)}>{pct(m.yoy, 0)}</td>
              </>}
            </tr>
          ))}
        </tbody>
      </table>
      {r.flags.map((f, i) => <div key={i} className={`flag ${f.tone}`}>{f.text}</div>)}
    </>
  )
}

export function Bio({ b }) {
  if (!b) return null
  return (
    <div className="bio">
      <div className="who">{b.name}</div>
      {b.role_new && <div className="role">{b.role_new}</div>}
      {b.previous && <div className="role">Previously {b.previous}</div>}
      {b.career?.length > 0 && <ul>{b.career.map((c, i) => <li key={i}>{c}</li>)}</ul>}
      {b.education && <div className="role" style={{ marginTop: 6 }}>{b.education}</div>}
      {b.succeeds && <div className="role" style={{ marginTop: 6 }}>Succeeds {b.succeeds}</div>}
      {b.so_what && <div className="sowhat">{b.so_what}</div>}
      <div className="srcs">{(b.sources || []).map((s, i) => <a key={i} href={s.url} target="_blank" rel="noreferrer">{s.title}</a>)}</div>
    </div>
  )
}

export const Icon = {
  brief: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M5 4h11l3 3v13H5z" /><path d="M8 10h8M8 14h8M8 18h5" /></svg>,
  alert: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M3 17l5-6 4 3 6-8" /><path d="M14 6h4v4" /></svg>,
  ask: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="11" cy="11" r="6" /><path d="M20 20l-4.5-4.5" /></svg>,
  book: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 5h16v14H4z" /><path d="M4 9h16M10 9v10" /></svg>,
  mic: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0014 0M12 18v3" /></svg>,
  go: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M13 6l6 6-6 6" /></svg>,
}
