// Data loading: live backend if reachable, otherwise the frozen snapshot shipped with the app.
export async function loadBundle() {
  try {
    const ctl = new AbortController()
    const t = setTimeout(() => ctl.abort(), 3500)
    const r = await fetch('/api/bundle', { signal: ctl.signal })
    clearTimeout(t)
    if (r.ok && (r.headers.get('content-type') || '').includes('json')) return { ...(await r.json()), live: true }
  } catch (e) { /* fall through */ }
  const r = await fetch('./snapshot.json')
  return { ...(await r.json()), live: false }
}

export async function liveResearch(sym) {
  const r = await fetch(`/api/research/${encodeURIComponent(sym)}`)
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `No data for ${sym}`)
  return r.json()
}

export const store = {
  get(k, d) { try { const v = localStorage.getItem('finn:' + k); return v ? JSON.parse(v) : d } catch { return d } },
  set(k, v) { try { localStorage.setItem('finn:' + k, JSON.stringify(v)) } catch { /* private mode */ } },
}

export const fmtCr = v => v == null ? '—' : v >= 100000 ? `₹${(v / 100000).toFixed(2)} L Cr` : `₹${Math.round(v).toLocaleString('en-IN')} Cr`
export const fmtN = v => v == null ? '—' : Math.round(v).toLocaleString('en-IN')
export const fmtPx = v => v == null ? '—' : `₹${v.toLocaleString('en-IN', { maximumFractionDigits: v < 1000 ? 2 : 0 })}`
export const pct = (v, d = 1) => v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(d)}%`
export const tone = v => v == null ? '' : v > 0 ? 'up' : v < 0 ? 'dn' : ''

export function daysBetween(a, b) { return Math.round((new Date(b) - new Date(a)) / 864e5) }
export function ago(date, asOf) {
  const d = daysBetween(date, asOf)
  if (d <= 0) return 'Today'
  if (d === 1) return 'Yesterday'
  if (d < 7) return new Date(date).toLocaleDateString('en-IN', { weekday: 'short' })
  return new Date(date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
}

export const WINDOWS = [
  { h: 24, label: 'Last 24h' }, { h: 72, label: '3 days' }, { h: 168, label: 'This week' }, { h: 720, label: '30 days' },
]
export function inWindow(item, asOf, hours) {
  return daysBetween(item.date, asOf) < Math.max(1, hours / 24)
}

// Rescore a filing against the user's own "care" list (backend scores with defaults).
export function personalise(item, care) {
  const base = item.score - (DEFAULT_CARE.includes(item.bucket) ? 10 : 0)
  const s = Math.max(0, Math.min(100, base + (care.includes(item.bucket) ? 10 : 0)))
  return { ...item, score: s, tier: s >= 65 ? 'act' : s >= 35 ? 'know' : 'routine' }
}
export const DEFAULT_CARE = ['results', 'M&A', 'fund_raise', 'management_change', 'litigation', 'insider_trading', 'pledging', 'credit_rating']
export const CARE_LABELS = {
  results: 'Results', 'M&A': 'M&A', fund_raise: 'Fund raise', management_change: 'Management', litigation: 'Legal',
  insider_trading: 'Insider / promoter', pledging: 'Pledges', credit_rating: 'Ratings', capex: 'Capex',
  press_release: 'Orders & news', dividend: 'Dividends', bonus_split: 'Bonus / split', earnings_call: 'Concalls',
}

// EOD rules, recomputed on-device so thresholds respond instantly (and work offline).
export function eodAlerts(series, volMult, look, move, days = 5) {
  const out = []
  for (let t = Math.max(look + 1, series.length - days); t < series.length; t++) {
    const d = series[t], p = series[t - 1]
    const avg = series.slice(t - look, t).reduce((a, x) => a + x.volume, 0) / look
    const vm = d.volume / avg, mv = (d.close / p.close - 1) * 100
    const hits = []
    if (vm >= volMult) hits.push({ rule: 'volume', text: `Volume ${vm.toFixed(1)}× its ${look}-day average` })
    if (Math.abs(mv) >= move) hits.push({ rule: 'price', text: `${mv > 0 ? 'Up' : 'Down'} ${Math.abs(mv).toFixed(1)}% on the day` })
    if (hits.length) out.push({ date: d.date, close: d.close, mv, vm, hits })
  }
  return out
}

const INTENTS = [
  ['guidance', /promis|guid|deliver|narrative|said|management|concall|call/i],
  ['cash', /cash|convert|fcf|cfo|quality/i],
  ['balance', /debt|leverage|balance|working capital|borrow/i],
  ['trajectory', /trend|trajector|growth|grow|margin|multi-?year/i],
  ['bullbear', /bull|bear|case|thesis|should/i],
  ['numbers', /result|quarter|number|revenue|profit|pat|ebitda|snapshot/i],
]
export function parseAsk(q, research) {
  const up = q.toUpperCase()
  const syms = Object.keys(research).sort((a, b) => b.length - a.length)
  let sym = syms.find(s => new RegExp(`\\b${s}\\b`).test(up))
  if (!sym) sym = syms.find(s => {
    const n = (research[s].snapshot.name || '').toUpperCase().replace(/\b(LTD|LIMITED|INDIA|\(INDIA\)|INDUSTRIES|COMPANY)\b/g, '').trim()
    const first = n.split(/\s+/)[0]
    return first.length > 2 && up.includes(first)
  })
  if (!sym) { const m = q.match(/\b([A-Za-z][A-Za-z&-]{2,14})\b/g); sym = m ? m.find(w => w === w.toUpperCase()) : null }
  const intent = (INTENTS.find(([, rx]) => rx.test(q)) || ['numbers'])[0]
  return { sym, intent }
}
