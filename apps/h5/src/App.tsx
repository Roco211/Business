
import { useEffect, useMemo, useState } from 'react'
import { api, bootstrapContext, loadAuth, loginWithPhone, saveAuth } from './api'
import type { Activity, AiEmployee, AuthState, Confirmation, InventoryItem, LedgerEvent, Overview, StockItem, Suggestion } from './types'
import './styles.css'

type Page = 'dashboard' | 'products' | 'inventory' | 'ai' | 'tasks' | 'coming-soon'

type LoadState = 'idle' | 'loading' | 'ready' | 'error'

const navItems: { page: Page; label: string }[] = [
  { page: 'dashboard', label: '工作台' },
  { page: 'products', label: '商品管理' },
  { page: 'inventory', label: '库存管理' },
  { page: 'ai', label: 'AI助手' },
  { page: 'tasks', label: '任务中心' },
  { page: 'coming-soon', label: '客户/营销' }
]

function formatMoney(value: number | string) {
  const n = Number(value || 0)
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function App() {
  const [auth, setAuth] = useState<AuthState | null>(() => loadAuth())
  const [page, setPage] = useState<Page>('dashboard')
  const [state, setState] = useState<LoadState>('idle')
  const [error, setError] = useState('')
  const [overview, setOverview] = useState<Overview | null>(null)
  const [items, setItems] = useState<InventoryItem[]>([])
  const [stock, setStock] = useState<StockItem[]>([])
  const [events, setEvents] = useState<LedgerEvent[]>([])
  const [confirmations, setConfirmations] = useState<Confirmation[]>([])

  async function refresh(currentAuth = auth) {
    if (!currentAuth) return
    setState('loading')
    setError('')
    try {
      const [nextOverview, nextItems, nextStock, nextEvents, nextConfirmations] = await Promise.all([
        api.getOverview(currentAuth),
        api.listItems(currentAuth),
        api.listStock(currentAuth),
        api.listEvents(currentAuth),
        api.listConfirmations(currentAuth)
      ])
      setOverview(nextOverview)
      setItems(nextItems.items)
      setStock(nextStock.items)
      setEvents(nextEvents.events)
      setConfirmations(nextConfirmations.confirmations)
      setState('ready')
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败')
      setState('error')
    }
  }

  useEffect(() => { if (auth) void refresh(auth) }, [])

  async function handleLogin(phone: string, code: string) {
    setState('loading')
    setError('')
    try {
      const login = await loginWithPhone(phone, code)
      const nextAuth = await bootstrapContext(login.accessToken, login.refreshToken, login.accountId)
      saveAuth(nextAuth)
      setAuth(nextAuth)
      await refresh(nextAuth)
    } catch (err) {
      setState('error')
      setError(err instanceof Error ? err.message : '登录失败')
    }
  }

  function handleLogout() {
    saveAuth(null)
    setAuth(null)
    setOverview(null)
    setItems([])
    setStock([])
    setEvents([])
    setConfirmations([])
  }

  if (!auth) return <LoginScreen onLogin={handleLogin} error={error} loading={state === 'loading'} />

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-mark">Business</div>
        <div className="brand-subtitle">AI 五金店大管家</div>
        <nav className="nav-list">
          {navItems.map((item) => (
            <button key={item.page} className={page === item.page ? 'nav-item active' : 'nav-item'} onClick={() => setPage(item.page)}>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <button className="ghost-button" onClick={handleLogout}>退出登录</button>
      </aside>
      <main className="main-panel">
        <TopBar overview={overview} onRefresh={() => void refresh()} loading={state === 'loading'} />
        {error && <div className="error-banner">{error}</div>}
        {state === 'loading' && !overview ? <SkeletonHome /> : null}
        {page === 'dashboard' && overview && <Dashboard overview={overview} onNavigate={setPage} />}
        {page === 'products' && <ProductsPage auth={auth} items={items} onChanged={() => void refresh()} />}
        {page === 'inventory' && <InventoryPage auth={auth} items={items} stock={stock} events={events} onChanged={() => void refresh()} />}
        {page === 'ai' && <AiPage auth={auth} overview={overview} onChanged={() => void refresh()} />}
        {page === 'tasks' && <TasksPage auth={auth} confirmations={confirmations} onChanged={() => void refresh()} />}
        {page === 'coming-soon' && <ComingSoon />}
      </main>
    </div>
  )
}

function LoginScreen({ onLogin, error, loading }: { onLogin: (phone: string, code: string) => Promise<void>; error: string; loading: boolean }) {
  const [phone, setPhone] = useState('13800000000')
  const [code, setCode] = useState('888888')
  return (
    <div className="login-page">
      <section className="login-card">
        <div className="login-eyebrow">Business Commercial Console</div>
        <h1>AI 五金店大管家</h1>
        <p>正式PC/H5管理台，聚焦商品、库存、经营数据和AI确认闭环。</p>
        <label>手机号<input value={phone} onChange={(e) => setPhone(e.target.value)} /></label>
        <label>验证码<input value={code} onChange={(e) => setCode(e.target.value)} /></label>
        <button className="primary-button" disabled={loading} onClick={() => void onLogin(phone, code)}>{loading ? '登录中...' : '演示登录（888888）'}</button>
        {error && <div className="error-text">{error}</div>}
      </section>
    </div>
  )
}

function TopBar({ overview, onRefresh, loading }: { overview: Overview | null; onRefresh: () => void; loading: boolean }) {
  return (
    <header className="top-bar">
      <div>
        <div className="top-eyebrow">{overview?.store.plan_label || 'Business'}</div>
        <h2>{overview?.store.shop_name || '当前门店'}</h2>
      </div>
      <div className="top-actions">
        <span className="user-pill">{overview?.user.display_name || '店主'}</span>
        <button className="secondary-button" onClick={onRefresh} disabled={loading}>{loading ? '刷新中' : '刷新数据'}</button>
      </div>
    </header>
  )
}

function Dashboard({ overview, onNavigate }: { overview: Overview; onNavigate: (page: Page) => void }) {
  return (
    <div className="content-grid">
      <section className="hero-card">
        <div>
          <div className="ai-badge">AI运营协调官</div>
          <h1>今天门店最重要的事情已整理好</h1>
          <p>所有经营指标来自后端真实API；订单、客户、营销等未实现模块暂不展示假数据。</p>
        </div>
        <button className="primary-button" onClick={() => onNavigate('ai')}>交给AI运营协调官处理</button>
      </section>
      <section className="kpi-grid">
        {overview.kpis.map((kpi) => <div className="kpi-card" key={kpi.key}><span>{kpi.label}</span><strong>{kpi.unit === '元' ? formatMoney(kpi.value) : kpi.value}</strong><em>{kpi.unit || ''}</em><p>{kpi.trend_label}</p></div>)}
      </section>
      <section className="two-column">
        <Panel title="今日重点事项">{overview.top_priorities.map((p) => <PriorityCard key={p.id} item={p} />)}</Panel>
        <Panel title="AI员工状态"><EmployeeGrid employees={overview.ai_employees} /></Panel>
      </section>
      <section className="two-column">
        <Panel title="AI智能建议"><SuggestionList suggestions={overview.suggestions} /></Panel>
        <Panel title="今日工作动态"><ActivityList activities={overview.activities} /></Panel>
      </section>
      <Panel title="商用版模块边界">
        <div className="coming-list">{overview.coming_soon_modules?.map((m) => <span key={m.key}>{m.label} 即将上线</span>)}</div>
      </Panel>
    </div>
  )
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) { return <section className="panel"><h3>{title}</h3>{children}</section> }
function PriorityCard({ item }: { item: { title: string; reason: string; severity: string; evidence: string[] } }) { return <div className={`priority-card ${item.severity}`}><strong>{item.title}</strong><p>{item.reason}</p><small>{item.evidence.join(' / ')}</small></div> }
function EmployeeGrid({ employees }: { employees: AiEmployee[] }) { return <div className="employee-grid">{employees.map((e) => <div className="employee-card" key={e.key}><b>{e.name}</b><span>{e.description}</span><em>{e.status}</em></div>)}</div> }
function SuggestionList({ suggestions }: { suggestions: Suggestion[] }) { return <div className="stack-list">{suggestions.map((s) => <div className="suggestion-card" key={s.id}><b>{s.title}</b><p>{s.summary}</p><small>依据：{s.evidence.join('；')}｜风险：{s.risk}</small></div>)}</div> }
function ActivityList({ activities }: { activities: Activity[] }) { return <div className="stack-list">{activities.map((a) => <div className="activity-row" key={a.id}><span>{a.time_label}</span><b>{a.actor_name}</b><p>{a.summary}，{a.impact}</p></div>)}</div> }

function ProductsPage({ auth, items, onChanged }: { auth: AuthState; items: InventoryItem[]; onChanged: () => void }) {
  const [name, setName] = useState('')
  const [sku, setSku] = useState('')
  async function create() { if (!name.trim()) return; await api.createItem(auth, { name, sku, default_unit: '个' }); setName(''); setSku(''); onChanged() }
  async function remove(id: string) { await api.deleteItem(auth, id); onChanged() }
  return <Panel title="商品管理"><div className="inline-form"><input placeholder="商品名称" value={name} onChange={(e) => setName(e.target.value)} /><input placeholder="SKU" value={sku} onChange={(e) => setSku(e.target.value)} /><button className="primary-button" onClick={() => void create()}>新增商品</button></div><DataTable rows={items} columns={['name','sku','default_unit','status']} action={(row) => <button className="danger-button" onClick={() => void remove(row.inventory_item_id)}>软删除</button>} /></Panel>
}

function InventoryPage({ auth, items, stock, events, onChanged }: { auth: AuthState; items: InventoryItem[]; stock: StockItem[]; events: LedgerEvent[]; onChanged: () => void }) {
  const firstItem = items[0]
  async function stockIn() { if (!firstItem) return; await api.stockIn(auth, { inventory_item_id: firstItem.inventory_item_id, quantity: 1, unit: firstItem.default_unit, price: 1, reason: 'PC/H5手动入库' }); onChanged() }
  async function stockOut() { if (!firstItem) return; await api.stockOut(auth, { inventory_item_id: firstItem.inventory_item_id, quantity: 1, unit: firstItem.default_unit, price: 1, reason: 'PC/H5手动出库' }); onChanged() }
  return <div className="content-grid"><Panel title="库存操作"><div className="inline-form"><button className="primary-button" disabled={!firstItem} onClick={() => void stockIn()}>对首个商品入库1</button><button className="secondary-button" disabled={!firstItem} onClick={() => void stockOut()}>对首个商品出库1</button></div></Panel><Panel title="库存快照"><DataTable rows={stock} columns={['item_name','current_quantity','low_stock_threshold','default_unit']} /></Panel><Panel title="库存流水"><DataTable rows={events} columns={['item_name','event_type','quantity_delta','quantity_after','reason']} /></Panel></div>
}

function AiPage({ auth, overview, onChanged }: { auth: AuthState; overview: Overview | null; onChanged: () => void }) {
  const [message, setMessage] = useState('查一下今天销售额')
  const [reply, setReply] = useState('')
  async function send() { const data = await api.chat(auth, message); setReply(data.reply); onChanged() }
  return <div className="content-grid"><section className="hero-card"><div><div className="ai-badge">AI运营协调官</div><h1>自然语言经营入口</h1><p>可查询营业数据、库存、热销排行；涉及库存写入时后端会生成待确认任务。</p></div></section><Panel title="问AI运营协调官"><div className="chat-box"><textarea value={message} onChange={(e) => setMessage(e.target.value)} /><button className="primary-button" onClick={() => void send()}>发送</button>{reply && <div className="assistant-reply">{reply}</div>}</div></Panel><Panel title="建议快捷入口"><SuggestionList suggestions={overview?.suggestions || []} /></Panel></div>
}

function TasksPage({ auth, confirmations, onChanged }: { auth: AuthState; confirmations: Confirmation[]; onChanged: () => void }) {
  async function approve(id: string) { await api.approveConfirmation(auth, id); onChanged() }
  async function reject(id: string) { await api.rejectConfirmation(auth, id); onChanged() }
  return <Panel title="AI待确认任务">{confirmations.length === 0 ? <Empty text="暂无待确认AI任务。" /> : <div className="stack-list">{confirmations.map((c) => <div className="task-card" key={c.confirmation_id}><b>{c.confirmation_type}</b><pre>{JSON.stringify(c.draft_payload, null, 2)}</pre><button className="primary-button" onClick={() => void approve(c.confirmation_id)}>批准落账</button><button className="secondary-button" onClick={() => void reject(c.confirmation_id)}>拒绝</button></div>)}</div>}</Panel>
}

function ComingSoon() { return <Panel title="即将上线"><Empty text="客户、订单、客服、营销、售后、财务等模块需要后端领域模型完成后再开放。当前商用试运行先聚焦商品、库存和AI经营助手。" /></Panel> }
function Empty({ text }: { text: string }) { return <div className="empty-state">{text}</div> }
function SkeletonHome() { return <div className="skeleton"><span /><span /><span /></div> }

function DataTable<T extends Record<string, unknown>>({ rows, columns, action }: { rows: T[]; columns: string[]; action?: (row: T) => React.ReactNode }) {
  if (!rows.length) return <Empty text="暂无数据，完成业务操作后这里会自动更新。" />
  return <div className="table-wrap"><table><thead><tr>{columns.map((c) => <th key={c}>{c}</th>)}{action && <th>操作</th>}</tr></thead><tbody>{rows.map((row, index) => <tr key={String(row.id || row.inventory_item_id || row.event_id || index)}>{columns.map((c) => <td key={c}>{String(row[c] ?? '-')}</td>)}{action && <td>{action(row)}</td>}</tr>)}</tbody></table></div>
}

export default App
