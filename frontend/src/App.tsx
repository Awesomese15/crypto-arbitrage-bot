import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Activity, ArrowDownToLine, CircleStop, Play, RefreshCw, ShieldCheck, Wifi } from 'lucide-react'

const API = 'http://127.0.0.1:8000/api'
type Route = { route: string; final_usdt: string | null; net_pct: string | null; gross_pct_estimate: string | null; status: string; reason: string }
type Book = { best_bid: string | null; best_ask: string | null; spread: string | null; last_update_id: number; received_at: string }
type Scan = { scan_finished_at: string; receive_time_skew_seconds: number; books: Record<string, Book>; routes: Route[] }
type Status = { running: boolean; config: { starting_amount: string; fee_rate: string; safety_threshold_pct: string; poll_interval_seconds: number; receive_skew_threshold_seconds: number }; latest_scan: Scan | null; last_error: string | null }
type Observation = Record<string, string>

const labelRoute = (route: string) => route.startsWith('Route A') ? 'Route A' : 'Route B'
const pct = (value: string | null) => value == null ? 'Unavailable' : `${Number(value).toFixed(4)}%`
const money = (value: string | null) => value == null ? 'Unavailable' : `${Number(value).toFixed(6)} USDT`

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, { headers: { 'Content-Type': 'application/json' }, ...options })
  const body = await response.json()
  if (!response.ok) throw new Error(body.detail ?? 'Request failed')
  return body
}

function App() {
  const [status, setStatus] = useState<Status | null>(null)
  const [observations, setObservations] = useState<Observation[]>([])
  const [routeFilter, setRouteFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [form, setForm] = useState({ starting_amount: '100', fee_rate: '0.001', safety_threshold_pct: '0.05', poll_interval_seconds: '5' })

  const load = useCallback(async () => {
    try {
      const [nextStatus, history] = await Promise.all([
        request<Status>('/status'),
        request<{ observations: Observation[] }>(`/observations?limit=50${routeFilter ? `&route=${encodeURIComponent(routeFilter)}` : ''}${statusFilter ? `&status=${encodeURIComponent(statusFilter)}` : ''}`),
      ])
      setStatus(nextStatus); setObservations(history.observations); setError(nextStatus.last_error ?? '')
    } catch (err) { setError(err instanceof Error ? err.message : 'Dashboard API unavailable') }
  }, [routeFilter, statusFilter])

  useEffect(() => { void load(); const timer = window.setInterval(() => void load(), 5000); return () => window.clearInterval(timer) }, [load])
  const action = async (path: string) => { setBusy(true); setError(''); try { await request(path, { method: 'POST' }); await load() } catch (err) { setError(err instanceof Error ? err.message : 'Action failed') } finally { setBusy(false) } }
  const saveConfig = async () => { setBusy(true); setError(''); try { await request('/config', { method: 'POST', body: JSON.stringify({ starting_amount: Number(form.starting_amount), fee_rate: Number(form.fee_rate), safety_threshold_pct: Number(form.safety_threshold_pct), poll_interval_seconds: Number(form.poll_interval_seconds) }) }); await load() } catch (err) { setError(err instanceof Error ? err.message : 'Configuration update failed') } finally { setBusy(false) } }

  const scan = status?.latest_scan
  const routes = scan?.routes ?? []
  const routeA = routes.find((r) => labelRoute(r.route) === 'Route A')
  const routeB = routes.find((r) => labelRoute(r.route) === 'Route B')
  const config = status?.config

  return <div className="app-shell">
    <header className="topbar"><div className="brand"><div className="brand-mark"><Activity size={19} /></div><div><div className="eyebrow">BINANCE / PUBLIC DATA</div><h1>Triangular Monitor</h1></div></div><div className="top-actions"><span className="safety"><ShieldCheck size={15} /> Observation only</span><button className="icon-button" onClick={() => void load()}><RefreshCw size={16} /></button></div></header>
    <main>
      <section className="hero"><div><div className="eyebrow">MARKET INTELLIGENCE</div><h2>Arbitrage radar</h2><p>Research-grade route observations with execution safeguards enabled.</p></div><div className="control-row"><button className="button primary" disabled={busy || status?.running} onClick={() => void action('/monitor/start')}><Play size={16} /> Start monitoring</button><button className="button" disabled={busy || !status?.running} onClick={() => void action('/monitor/stop')}><CircleStop size={16} /> Stop</button><button className="button" disabled={busy || status?.running} onClick={() => void action('/scan')}><ArrowDownToLine size={16} /> One-shot scan</button></div></section>
      {error && <div className="alert">{error}</div>}
      <section className="config-strip"><div><div className="eyebrow">SCAN CONFIGURATION</div><strong>Observation inputs</strong><span>Changes apply when monitoring is stopped.</span></div><label>Amount (USDT)<input type="number" min="0.000001" step="any" value={form.starting_amount} onChange={(e) => setForm({ ...form, starting_amount: e.target.value })} /></label><label>Fee / leg<input type="number" min="0" max="1" step="0.0001" value={form.fee_rate} onChange={(e) => setForm({ ...form, fee_rate: e.target.value })} /></label><label>Threshold (%)<input type="number" min="0" max="100" step="0.001" value={form.safety_threshold_pct} onChange={(e) => setForm({ ...form, safety_threshold_pct: e.target.value })} /></label><label>Polling (seconds)<input type="number" min="1" max="3600" step="1" value={form.poll_interval_seconds} onChange={(e) => setForm({ ...form, poll_interval_seconds: e.target.value })} /></label><button className="button" disabled={busy || status?.running} onClick={() => void saveConfig()}>Save config</button></section>
      <section className="cards"><Card title="Scanner status" value={status?.running ? 'Monitoring' : 'Idle'} meta={status?.running ? 'Polling public depth data' : 'Ready for observation'} tone={status?.running ? 'green' : 'neutral'} /><Card title="Latest scan" value={scan ? new Date(scan.scan_finished_at).toLocaleTimeString() : 'Unavailable'} meta={scan ? new Date(scan.scan_finished_at).toLocaleDateString() : 'No scan recorded'} /><Card title="Starting amount" value={config ? `${config.starting_amount} USDT` : 'Unavailable'} meta="Observation input" /><Card title="Receive-time skew" value={scan ? `${scan.receive_time_skew_seconds.toFixed(3)}s` : 'Unavailable'} meta={scan ? `Guard: ${config?.receive_skew_threshold_seconds}s` : 'Client timestamps only'} tone={scan && config && scan.receive_time_skew_seconds > config.receive_skew_threshold_seconds ? 'red' : 'neutral'} /></section>
      <section className="grid-two"><Panel title="Route comparison" subtitle="Simulated estimates after assumed fees"><div className="route-grid"><RouteCard route={routeA} /><RouteCard route={routeB} /></div></Panel><Panel title="Market overview" subtitle="Best levels from latest public depth fetch"><div className="market-list">{Object.entries(scan?.books ?? {}).map(([symbol, book]) => <div className="market-row" key={symbol}><div><strong>{symbol}</strong><span className="muted">Update {book.last_update_id} · spread {book.spread ?? '—'}</span></div><div className="quote"><span className="bid">{book.best_bid ?? '—'}</span><span className="ask">{book.best_ask ?? '—'}</span><small>{new Date(book.received_at).toLocaleTimeString()}</small></div></div>)}{!scan && <div className="empty">Run a scan to load market data.</div>}</div></Panel></section>
      <Panel title="Observation history" subtitle="Read-only view of paper_observations.csv"><div className="filters"><select value={routeFilter} onChange={(e) => setRouteFilter(e.target.value)}><option value="">All routes</option><option value="Route A: USDT → BTC → ETH → USDT">Route A: USDT → BTC → ETH → USDT</option><option value="Route B: USDT → ETH → BTC → USDT">Route B: USDT → ETH → BTC → USDT</option></select><select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}><option value="">All statuses</option><option>CANDIDATE</option><option>REJECTED</option><option>INCOMPLETE</option></select></div><div className="table-wrap"><table><thead><tr><th>Timestamp</th><th>Route</th><th>Status</th><th>Estimated ending</th><th>Return</th><th>Reason</th></tr></thead><tbody>{observations.map((row, index) => <tr key={`${row.timestamp}-${index}`}><td>{row.timestamp ? new Date(row.timestamp).toLocaleString() : '—'}</td><td>{labelRoute(row.route)}</td><td><span className={`status ${row.status?.toLowerCase()}`}>{row.status}</span></td><td>{money(row.estimated_ending_balance || null)}</td><td>{pct(row.return_pct || null)}</td><td className="muted">{row.reason || '—'}</td></tr>)}</tbody></table>{!observations.length && <div className="empty">No observations match the current filters.</div>}</div></Panel>
      <footer><Wifi size={14} /> Local dashboard · backend expected at 127.0.0.1 · Real orders disabled</footer>
    </main>
  </div>
}

function Card({ title, value, meta, tone = 'neutral' }: { title: string; value: string; meta: string; tone?: string }) { return <div className="card"><div className="card-title">{title}</div><div className={`card-value ${tone}`}>{value}</div><div className="card-meta">{meta}</div></div> }
function Panel({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) { return <section className="panel"><div className="panel-heading"><div><h3>{title}</h3><p>{subtitle}</p></div></div>{children}</section> }
function RouteCard({ route }: { route?: Route }) { return <div className="route-card"><div className="route-heading"><div><span className="route-label">{route ? labelRoute(route.route) : 'Route unavailable'}</span><strong>{route?.route?.includes('BTC -> ETH') ? 'USDT → BTC → ETH → USDT' : 'USDT → ETH → BTC → USDT'}</strong></div><span className={`status ${route?.status.toLowerCase() ?? 'unavailable'}`}>{route?.status ?? 'UNAVAILABLE'}</span></div><div className="route-metrics"><div><span>Net return</span><b>{pct(route?.net_pct ?? null)}</b></div><div><span>Ending balance</span><b>{money(route?.final_usdt ?? null)}</b></div><div><span>Gross estimate</span><b>{pct(route?.gross_pct_estimate ?? null)}</b></div></div><div className="route-note">{route?.reason || 'Assumed fee model applied · simulated estimate only'}</div></div> }

export default App
