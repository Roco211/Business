
import { useEffect, useMemo, useRef, useState } from 'react'
import { api, bootstrapContext, loadAuth, loginWithPhone, saveAuth } from './api'
import type { Activity, AiEmployee, AuthState, Confirmation, Customer, CustomerRepurchaseAnalysis, DailyAdvisorReport, ExecutionRecapList, FinanceSummary, FinanceTransaction, InventoryItem, LedgerEvent, NotificationItem, Overview, PurchaseOrder, SalesOrder, StockItem, Suggestion, Supplier } from './types'
import './styles.css'

type Page = 'dashboard' | 'daily-report' | 'execution-recaps' | 'trial-acceptance' | 'sales' | 'purchasing' | 'customers' | 'finance' | 'products' | 'inventory' | 'ai' | 'tasks' | 'coming-soon'

type LoadState = 'idle' | 'loading' | 'ready' | 'error'

type NavItem = { page: Page; label: string; icon: string; badge?: string; permission?: string }

const navItems: NavItem[] = [
  { page: 'dashboard', label: '工作台', icon: '⌂' },
  { page: 'ai', label: '我的员工', icon: '◇' },
  { page: 'daily-report', label: '经营日报', icon: '◌', badge: 'AI' },
  { page: 'execution-recaps', label: '执行复盘', icon: '◎', badge: 'AI' },
  { page: 'trial-acceptance', label: '试运行验收', icon: '✓' },
  { page: 'sales', label: '销售单', icon: '□', permission: 'sales:read' },
  { page: 'purchasing', label: '采购单', icon: '▣', permission: 'purchasing:read' },
  { page: 'customers', label: '客户复购', icon: '◎', permission: 'customers:read' },
  { page: 'products', label: '商品管理', icon: '▤', permission: 'inventory:read' },
  { page: 'inventory', label: '库存管理', icon: '▥', permission: 'inventory:read' },
  { page: 'finance', label: '财务流水', icon: '¥', permission: 'finance:read' },
  { page: 'tasks', label: '任务中心', icon: '✓', badge: 'AI' },
  { page: 'coming-soon', label: '营销/售后', icon: '✧' }
]

function formatMoney(value: number | string) {
  const n = Number(value || 0)
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function hasPermission(auth: AuthState | null, permission: string) {
  return Boolean(auth?.permissions?.includes(permission))
}

function roleLabel(roleKey?: string) {
  if (roleKey === 'owner') return '老板/管理员'
  if (roleKey === 'clerk') return '店员'
  if (roleKey === 'finance') return '财务'
  return roleKey || '未设置角色'
}

function permissionHint(permission?: string) {
  if (!permission) return ''
  if (permission.startsWith('finance')) return '需要财务或老板权限'
  if (permission.startsWith('inventory:write')) return '需要库存写入权限'
  if (permission.startsWith('confirmations')) return '需要老板审批权限'
  return '当前角色无权限'
}

function App() {
  const [auth, setAuth] = useState<AuthState | null>(() => loadAuth())
  const [page, setPage] = useState<Page>('dashboard')
  const [state, setState] = useState<LoadState>('idle')
  const [error, setError] = useState('')
  const [overview, setOverview] = useState<Overview | null>(null)
  const [dailyReport, setDailyReport] = useState<DailyAdvisorReport | null>(null)
  const [executionRecapList, setExecutionRecapList] = useState<ExecutionRecapList | null>(null)
  const [items, setItems] = useState<InventoryItem[]>([])
  const [stock, setStock] = useState<StockItem[]>([])
  const [events, setEvents] = useState<LedgerEvent[]>([])
  const [orders, setOrders] = useState<SalesOrder[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [purchaseOrders, setPurchaseOrders] = useState<PurchaseOrder[]>([])
  const [customers, setCustomers] = useState<Customer[]>([])
  const [repurchase, setRepurchase] = useState<CustomerRepurchaseAnalysis | null>(null)
  const [financeTransactions, setFinanceTransactions] = useState<FinanceTransaction[]>([])
  const [financeSummary, setFinanceSummary] = useState<FinanceSummary | null>(null)
  const [confirmations, setConfirmations] = useState<Confirmation[]>([])
  const [guideSignal, setGuideSignal] = useState(0)
  const [notificationOpen, setNotificationOpen] = useState(false)

  async function refresh(currentAuth = auth) {
    if (!currentAuth) return
    setState('loading')
    setError('')
    try {
      const canReadFinance = hasPermission(currentAuth, 'finance:read')
      const [nextOverview, nextDailyReport, nextExecutionRecapList, nextItems, nextStock, nextEvents, nextOrders, nextSuppliers, nextPurchaseOrders, nextCustomers, nextRepurchase, nextFinanceTransactions, nextFinanceSummary, nextConfirmations] = await Promise.all([
        api.getOverview(currentAuth),
        api.getDailyReport(currentAuth),
        api.getExecutionRecaps(currentAuth),
        api.listItems(currentAuth),
        api.listStock(currentAuth),
        api.listEvents(currentAuth),
        api.listSalesOrders(currentAuth),
        api.listSuppliers(currentAuth),
        api.listPurchaseOrders(currentAuth),
        api.listCustomers(currentAuth),
        api.getCustomerRepurchaseAnalysis(currentAuth),
        canReadFinance ? api.listFinanceTransactions(currentAuth) : Promise.resolve({ transactions: [], count: 0 }),
        canReadFinance ? api.getFinanceSummary(currentAuth) : Promise.resolve({ summary: null }),
        api.listConfirmations(currentAuth)
      ])
      setOverview(nextOverview)
      setDailyReport(nextDailyReport)
      setExecutionRecapList(nextExecutionRecapList)
      setItems(nextItems.items)
      setStock(nextStock.items)
      setEvents(nextEvents.events)
      setOrders(nextOrders.orders)
      setSuppliers(nextSuppliers.suppliers)
      setPurchaseOrders(nextPurchaseOrders.purchase_orders)
      setCustomers(nextCustomers.customers)
      setRepurchase(nextRepurchase)
      setFinanceTransactions(nextFinanceTransactions.transactions)
      setFinanceSummary(nextFinanceSummary.summary)
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
    setDailyReport(null)
    setExecutionRecapList(null)
    setItems([])
    setStock([])
    setEvents([])
    setOrders([])
    setSuppliers([])
    setPurchaseOrders([])
    setCustomers([])
    setRepurchase(null)
    setFinanceTransactions([])
    setFinanceSummary(null)
    setConfirmations([])
  }

  if (!auth) return <LoginScreen onLogin={handleLogin} error={error} loading={state === 'loading'} />

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-logo">AI</div>
          <div>
            <div className="brand-mark">AI数字员工</div>
            <div className="brand-subtitle">你的生意增长伙伴</div>
          </div>
        </div>
        <nav className="nav-list">
          {navItems.map((item) => {
            const allowed = !item.permission || hasPermission(auth, item.permission)
            return (
              <button key={item.page} className={`${page === item.page ? 'nav-item active' : 'nav-item'} ${allowed ? '' : 'locked'}`} disabled={!allowed} title={allowed ? item.label : permissionHint(item.permission)} onClick={() => allowed && setPage(item.page)}>
                <span className="nav-icon">{item.icon}</span>
                <span className="nav-label">{item.label}</span>
                {item.badge && <span className="nav-badge">{item.badge}</span>}
                {!allowed && <span className="nav-lock">锁</span>}
              </button>
            )
          })}
        </nav>
        <div className="upgrade-card">
          <strong>升级老板版</strong>
          <p>解锁全部AI员工和高级经营分析</p>
          <button>立即升级 →</button>
        </div>
        <button className="ghost-button" onClick={handleLogout}>退出登录</button>
      </aside>
      <main className="main-panel">
        <TopBar auth={auth} overview={overview} onRefresh={() => void refresh()} loading={state === 'loading'} onGuide={() => { setPage('dashboard'); setGuideSignal((value) => value + 1) }} onNotifications={() => setNotificationOpen(true)} />
        {error && <div className="error-banner">{error}</div>}
        {state === 'loading' && !overview ? <SkeletonHome /> : null}
        {page === 'dashboard' && overview && <Dashboard auth={auth} overview={overview} onNavigate={setPage} onChanged={() => void refresh()} guideSignal={guideSignal} />}
        {page === 'daily-report' && dailyReport && <DailyReportPage report={dailyReport} onNavigate={setPage} />}
        {page === 'execution-recaps' && executionRecapList && <ExecutionRecapsPage data={executionRecapList} onNavigate={setPage} />}
        {page === 'trial-acceptance' && overview && <CommercialTrialAcceptancePage overview={overview} items={items} stock={stock} events={events} orders={orders} suppliers={suppliers} purchaseOrders={purchaseOrders} customers={customers} financeTransactions={financeTransactions} financeSummary={financeSummary} confirmations={confirmations} executionRecapList={executionRecapList} onNavigate={setPage} />}
        {page === 'sales' && <SalesPage auth={auth} stock={stock} orders={orders} customers={customers} onChanged={() => void refresh()} />}
        {page === 'purchasing' && <PurchasingPage auth={auth} stock={stock} suppliers={suppliers} purchaseOrders={purchaseOrders} onChanged={() => void refresh()} />}
        {page === 'customers' && <CustomersPage auth={auth} customers={customers} orders={orders} repurchase={repurchase} onChanged={() => void refresh()} />}
        {page === 'finance' && <FinancePage auth={auth} summary={financeSummary} transactions={financeTransactions} onTransactionsChanged={setFinanceTransactions} />}
        {page === 'products' && <ProductsPage auth={auth} items={items} onChanged={() => void refresh()} />}
        {page === 'inventory' && <InventoryPage auth={auth} items={items} stock={stock} events={events} onChanged={() => void refresh()} />}
        {page === 'ai' && <AiPage auth={auth} overview={overview} onChanged={() => void refresh()} />}
        {page === 'tasks' && <TasksPage auth={auth} confirmations={confirmations} onChanged={() => void refresh()} />}
        {page === 'coming-soon' && <ComingSoon />}
        {notificationOpen && overview && <NotificationCenter notifications={overview.notifications} onClose={() => setNotificationOpen(false)} onNavigate={(nextPage) => { setNotificationOpen(false); setPage(nextPage) }} />}
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


function AccessDenied({ title = '当前角色无权限', message = '请联系老板/管理员调整账号角色或切换到有权限的门店上下文。' }: { title?: string; message?: string }) {
  return <section className="access-denied-card"><div className="ai-badge">RBAC 权限保护</div><h1>{title}</h1><p>{message}</p><div className="permission-note">前端只做可见性提示，真实权限由后端接口强制校验。</div></section>
}

function TopBar({ auth, overview, onRefresh, loading, onGuide, onNotifications }: { auth: AuthState; overview: Overview | null; onRefresh: () => void; loading: boolean; onGuide: () => void; onNotifications: () => void }) {
  return (
    <header className="top-bar">
      <div className="greeting-block">
        <h2>早上好，老板！</h2>
        <p>AI员工们正在为你打理店铺，请查看今日经营概况</p>
      </div>
      <div className="top-actions">
        <button className="guide-button" onClick={onGuide}>新手引导</button>
        <button className="notification-trigger" onClick={onNotifications} aria-label="打开通知中心">
          <span>○</span>
          {(overview?.notifications.unread_count || 0) > 0 && <b>{overview?.notifications.unread_count}</b>}
        </button>
        <div className="store-profile">
          <div className="store-avatar">五</div>
          <div>
            <strong>{overview?.store.shop_name || '当前门店'}</strong>
            <small>{overview?.store.plan_label || '本地演示版'} · {overview?.user.display_name || '店主'}</small>
          </div>
        </div>
        <div className="role-chip" title={(auth.permissions || []).join(' / ')}>
          <span>当前角色</span>
          <strong>{roleLabel(auth.roleKey)}</strong>
        </div>
        <button className="secondary-button" onClick={onRefresh} disabled={loading}>{loading ? '刷新中' : '刷新数据'}</button>
      </div>
    </header>
  )
}

function NotificationCenter({ notifications, onClose, onNavigate }: { notifications: Overview['notifications']; onClose: () => void; onNavigate: (page: Page) => void }) {
  const items = notifications.items || []
  function severityLabel(severity: string) {
    if (severity === 'high') return '高优先级'
    if (severity === 'medium') return '需关注'
    return '普通'
  }
  return (
    <div className="notification-overlay">
      <div className="notification-backdrop" onClick={onClose} />
      <aside className="notification-drawer" role="dialog" aria-label="通知中心">
        <header className="notification-drawer-head">
          <div>
            <div className="ai-badge">通知中心</div>
            <h2>老板需要关注的事</h2>
            <p>{notifications.attention_count || 0} 个重点事项 · {notifications.unread_count || 0} 条未读</p>
          </div>
          <button className="drawer-close" onClick={onClose}>×</button>
        </header>
        <div className="notification-list">
          {items.length === 0 ? <div className="notification-empty">当前没有新的通知，AI员工会继续监控任务、库存和经营日报。</div> : items.map((item: NotificationItem) => (
            <article className={`notification-card severity-${item.severity}`} key={item.id}>
              <div className="notification-card-head">
                <span>{item.source_employee}</span>
                <b>{severityLabel(item.severity)}</b>
              </div>
              <h3>{item.title}</h3>
              <p>{item.summary}</p>
              <div className="notification-evidence">
                {item.evidence.slice(0, 3).map((evidence) => <small key={evidence}>{evidence}</small>)}
              </div>
              <button className="secondary-button" onClick={() => onNavigate(routeToPage(item.route))}>{item.action_label}</button>
            </article>
          ))}
        </div>
      </aside>
    </div>
  )
}

function Dashboard({ auth, overview, onNavigate, onChanged, guideSignal }: { auth: AuthState; overview: Overview; onNavigate: (page: Page) => void; onChanged: () => void; guideSignal: number }) {
  const guideRef = useRef<HTMLElement | null>(null)
  useEffect(() => {
    if (guideSignal > 0) guideRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [guideSignal])
  return (
    <div className="dashboard-layout">
      <AiCommandCenter auth={auth} onNavigate={onNavigate} onChanged={onChanged} />
      <OnboardingDemoFlow refEl={guideRef} auth={auth} onNavigate={onNavigate} onChanged={onChanged} />
      <section className="kpi-grid">
        {overview.kpis.map((kpi, index) => <KpiCard kpi={kpi} index={index} key={kpi.key} />)}
      </section>
      {overview.daily_advisor_report && <DailyAdvisorReportCard report={overview.daily_advisor_report} onNavigate={onNavigate} />}
      <section className="dashboard-main-grid">
        <Panel title="我的AI员工" action="查看全部">
          <EmployeeGrid employees={overview.ai_employees} />
        </Panel>
        <Panel title="AI智能建议" action="全部建议">
          <SuggestionList suggestions={overview.suggestions} />
        </Panel>
      </section>
      <section className="operations-grid">
        <Panel title="今日工作动态" action="查看报告">
          <ActivityList activities={overview.activities} />
        </Panel>
        <Panel title="待办事项" action={`${overview.top_priorities.length}项`}>
          {overview.top_priorities.map((p) => <PriorityCard key={p.id} item={p} />)}
        </Panel>
      </section>
      <section className="hero-card">
        <div>
          <div className="ai-badge">AI运营协调官</div>
          <h1>今天门店最重要的事情已整理好</h1>
          <p>所有经营指标来自后端真实API；未实现模块保持即将上线，不展示假数据。</p>
        </div>
        <button className="primary-button" onClick={() => onNavigate('ai')}>交给AI处理</button>
      </section>
      <Panel title="商用版模块边界">
        <div className="coming-list">{overview.coming_soon_modules?.map((m) => <span key={m.key}>{m.label} 即将上线</span>)}</div>
      </Panel>
    </div>
  )
}

type CommandResult = { kind: 'reply' | 'draft' | 'error'; title: string; body: string; meta?: string }

function AiCommandCenter({ auth, onNavigate, onChanged }: { auth: AuthState; onNavigate: (page: Page) => void; onChanged: () => void }) {
  const quickCommands = ['今天卖了多少钱？', '卖出1把电动螺丝刀，单价99，客户老王', '向默认五金供应商采购5把电动螺丝刀，单价10', '出库1把电动螺丝刀']
  const [command, setCommand] = useState(quickCommands[0])
  const [result, setResult] = useState<CommandResult | null>(null)
  const [running, setRunning] = useState(false)

  function looksLikeSalesDraft(text: string) {
    return /卖出|销售|开单|收款|客户/.test(text) && /单价|客户|把|个|件|箱|元|\d/.test(text)
  }

  function looksLikePurchaseDraft(text: string) {
    return /采购|进货|补货|向.*供应商/.test(text) && /单价|进价|成本|把|个|件|箱|元|\d/.test(text)
  }

  function looksLikeInventoryDraft(text: string) {
    return /入库|出库|盘出|盘入/.test(text) && /把|个|件|箱|\d/.test(text)
  }

  function extractConfirmationId(reply: string) {
    return reply.match(/确认单[:：]\s*(\S+)/)?.[1]
  }

  function normalizeQueryCommand(text: string) {
    if (/卖了多少钱|营业额|营收|收入|流水|赚了|利润/.test(text)) return '今天营业额多少？'
    if (/热销|排行|最好卖|卖得好/.test(text)) return '热销商品排行'
    if (/快没货|缺货|库存不足|预警/.test(text)) return '库存预警'
    return text
  }

  async function runCommand(text = command) {
    const trimmed = text.trim()
    if (!trimmed || running) return
    setCommand(trimmed)
    setRunning(true)
    setResult({ kind: 'reply', title: 'AI运营协调官正在分派任务', body: '正在理解你的经营指令，并交给对应AI员工处理。' })
    try {
      if (looksLikePurchaseDraft(trimmed)) {
        const data = await api.createPurchaseOrderDraft(auth, trimmed)
        setResult({
          kind: 'draft',
          title: '已生成采购入库草稿，等待老板确认',
          body: `待确认任务 ${data.confirmation.confirmation_id} 已创建。AI不会直接入库或记采购支出，请到任务中心确认后再落账。`,
          meta: data.confirmation.confirmation_type
        })
      } else if (looksLikeSalesDraft(trimmed)) {
        const data = await api.createSalesOrderDraft(auth, trimmed)
        setResult({
          kind: 'draft',
          title: '已生成销售单草稿，等待老板确认',
          body: `待确认任务 ${data.confirmation.confirmation_id} 已创建。AI不会直接扣库存或记账，请到任务中心确认后再落账。`,
          meta: data.confirmation.confirmation_type
        })
      } else if (looksLikeInventoryDraft(trimmed)) {
        const data = await api.chat(auth, trimmed)
        const confirmationId = extractConfirmationId(data.reply || '')
        setResult({
          kind: confirmationId ? 'draft' : 'reply',
          title: confirmationId ? '已生成库存变动草稿，等待老板确认' : employeeNameForIntent(data.intent || '') + '已完成处理',
          body: confirmationId ? `待确认任务 ${confirmationId} 已创建。AI不会直接改库存，请到任务中心确认后再落账。` : (data.reply || '已收到库存指令。'),
          meta: data.intent || 'inventory'
        })
      } else {
        const queryMessage = normalizeQueryCommand(trimmed)
        const data = await api.chat(auth, queryMessage)
        setResult({
          kind: 'reply',
          title: employeeNameForIntent(data.intent || '') + '已完成处理',
          body: data.reply || '已收到指令，但暂时没有可展示的回复。',
          meta: data.intent || 'general'
        })
      }
      onChanged()
    } catch (err) {
      setResult({ kind: 'error', title: 'AI任务处理失败', body: err instanceof Error ? err.message : '请稍后重试。' })
    } finally {
      setRunning(false)
    }
  }

  return (
    <section className="command-center-card">
      <div className="command-copy">
        <div className="ai-badge">AI Command Center</div>
        <h1>老板，今天想让我帮你做什么？</h1>
        <p>直接说经营目标。查询类任务由AI员工返回结果；开单、库存、采购等高风险动作先生成待确认草稿。</p>
      </div>
      <div className="command-console">
        <div className="command-input-row">
          <textarea value={command} onChange={(e) => setCommand(e.target.value)} placeholder="例如：今天卖了多少钱？或者：卖出1把电动螺丝刀，单价99，客户老王" />
          <button className="primary-button" disabled={running || !command.trim()} onClick={() => void runCommand()}>{running ? '处理中...' : '交给AI员工'}</button>
        </div>
        <div className="command-chips">
          {quickCommands.map((text) => <button key={text} onClick={() => void runCommand(text)} disabled={running}>{text}</button>)}
        </div>
        {result && <div className={`command-result ${result.kind}`}>
          <strong>{result.title}</strong>
          <p>{result.body}</p>
          {result.meta && <small>任务类型：{result.meta}</small>}
          {result.kind === 'draft' && <button className="secondary-button" onClick={() => onNavigate('tasks')}>去任务中心确认</button>}
        </div>}
      </div>
    </section>
  )
}

type DemoFlowStep = {
  key: string
  title: string
  description: string
  status: 'ready' | 'done' | 'manual'
}

function OnboardingDemoFlow({ refEl, auth, onNavigate, onChanged }: { refEl: React.RefObject<HTMLElement | null>; auth: AuthState; onNavigate: (page: Page) => void; onChanged: () => void }) {
  const [running, setRunning] = useState(false)
  const [revenueReply, setRevenueReply] = useState('')
  const [confirmationId, setConfirmationId] = useState('')
  const [error, setError] = useState('')

  async function runOneClickDemo() {
    if (running) return
    setRunning(true)
    setError('')
    setRevenueReply('')
    setConfirmationId('')
    try {
      const revenue = await api.chat(auth, '今天营业额多少？')
      setRevenueReply(revenue.reply || '经营数据分析员已完成营业额查询。')
      const draft = await api.createSalesOrderDraft(auth, '卖出1把电动螺丝刀，单价99，客户老王')
      setConfirmationId(draft.confirmation.confirmation_id)
      await onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : '一键演示失败，请稍后重试。')
    } finally {
      setRunning(false)
    }
  }

  const steps: DemoFlowStep[] = [
    { key: 'query', title: '1. 查经营结果', description: revenueReply || '先让经营数据分析员查询今日营业额。', status: revenueReply ? 'done' : 'ready' },
    { key: 'draft', title: '2. 生成销售草稿', description: confirmationId ? `已生成待确认任务 ${confirmationId}` : '再让销售分析员生成销售单草稿。', status: confirmationId ? 'done' : 'ready' },
    { key: 'confirm', title: '3. 老板确认执行', description: '进入任务中心，查看风险、证据和影响后手动确认。', status: confirmationId ? 'manual' : 'ready' },
    { key: 'recap', title: '4. 查看执行复盘', description: '确认后页面会展示已创建销售单、已扣减库存、已记录销售收入。', status: 'manual' }
  ]

  return (
    <section className="onboarding-demo-card" ref={refEl}>
      <div className="onboarding-copy">
        <div className="ai-badge">新手引导</div>
        <h2>老板一分钟体验流程</h2>
        <p>从一句话经营查询开始，自动生成销售草稿；真正落账前仍然必须由老板在任务中心确认。</p>
        <div className="onboarding-actions">
          <button className="primary-button" onClick={() => void runOneClickDemo()} disabled={running}>{running ? '演示中...' : '开始一键演示'}</button>
          <button className="secondary-button" onClick={() => onNavigate('tasks')} disabled={!confirmationId}>去任务中心确认</button>
        </div>
        {error && <div className="onboarding-error">{error}</div>}
      </div>
      <div className="onboarding-steps">
        {steps.map((step) => <div className={`onboarding-step ${step.status}`} key={step.key}>
          <span>{step.status === 'done' ? '完成' : step.status === 'manual' ? '手动' : '准备'}</span>
          <strong>{step.title}</strong>
          <p>{step.description}</p>
        </div>)}
      </div>
    </section>
  )
}

function employeeNameForIntent(intent: string) {
  if (intent.includes('revenue')) return '经营数据分析员'
  if (intent.includes('sales')) return '销售分析员'
  if (intent.includes('alert') || intent.includes('stock') || intent.includes('inventory')) return '库存风控专员'
  if (intent.includes('purchase')) return '采购专员'
  return 'AI运营协调官'
}

function routeToPage(route: string): Page {
  if (route.includes('/execution-recaps')) return 'execution-recaps'
  if (route.includes('/daily-report')) return 'daily-report'
  if (route.includes('/tasks')) return 'tasks'
  if (route.includes('/inventory')) return 'inventory'
  if (route.includes('/products')) return 'products'
  if (route.includes('/sales')) return 'sales'
  if (route.includes('/purchasing')) return 'purchasing'
  if (route.includes('/finance')) return 'finance'
  if (route.includes('/ai')) return 'ai'
  return 'dashboard'
}

function DailyAdvisorReportCard({ report, onNavigate }: { report: NonNullable<Overview['daily_advisor_report']>; onNavigate: (page: Page) => void }) {
  const healthLabel = report.business_health === 'attention_needed' ? '需要老板关注' : report.business_health === 'healthy' ? '经营平稳' : '数据较少'
  return (
    <section className={`daily-report-card ${report.business_health}`}>
      <div className="daily-report-head">
        <div>
          <div className="ai-badge">{report.generated_by}</div>
          <h2>{report.title}</h2>
          <p>{report.summary}</p>
        </div>
        <span className="report-health-pill">{healthLabel}</span>
      </div>
      <div className="daily-report-sections">
        {report.sections.map((section) => <div className="daily-report-section" key={section.key}>
          <small>{section.employee}</small>
          <strong>{section.title}</strong>
          <p>{section.content}</p>
        </div>)}
      </div>
      <div className="daily-report-bottom">
        <div className="report-next-actions">
          <span>下一步建议</span>
          {report.next_actions.slice(0, 3).map((action) => <button key={`${action.title}-${action.route}`} onClick={() => onNavigate(routeToPage(action.route))}>
            <b>{action.title}</b>
            <small>{action.label}</small>
          </button>)}
          <button onMouseDown={() => onNavigate('daily-report')} onTouchStart={() => onNavigate('daily-report')} onClick={() => onNavigate('daily-report')}>
            <b>查看完整AI经营日报</b>
            <small>看详情</small>
          </button>
        </div>
        <div className="report-risk-notes">
          <span>风险提醒</span>
          {report.risk_notes.slice(0, 3).map((note) => <p key={note}>□ {note}</p>)}
        </div>
      </div>
    </section>
  )
}

function DailyReportPage({ report, onNavigate }: { report: DailyAdvisorReport; onNavigate: (page: Page) => void }) {
  const healthLabel = report.business_health === 'attention_needed' ? '需要老板关注' : report.business_health === 'healthy' ? '经营平稳' : '数据较少'
  const history = report.history || []
  const recaps = report.execution_recaps || []
  const timeline = report.timeline || []
  return (
    <section className="daily-detail-page">
      <div className="page-heading daily-detail-hero">
        <div>
          <span className="ai-badge">{report.generated_by}</span>
          <h1>AI经营日报</h1>
          <p>{report.summary}</p>
          <small>日报日期：{report.report_date || '今日'} · 生成时间：{report.generated_at || '实时生成'}</small>
        </div>
        <div className={`daily-health-orb ${report.business_health}`}>
          <strong>{healthLabel}</strong>
          <span>AI已完成复盘</span>
        </div>
      </div>
      <div className="daily-detail-grid">
        <div className="daily-detail-main">
          <Panel title="多AI员工复盘">
            <div className="daily-detail-sections">
              {report.sections.map((section) => <article className="daily-detail-section" key={section.key}>
                <small>{section.employee}</small>
                <h3>{section.title}</h3>
                <p>{section.content}</p>
                <div className="mini-metrics">
                  {Object.entries(section.metrics || {}).map(([key, value]) => <span key={key}>{key}<b>{value}</b></span>)}
                </div>
              </article>)}
            </div>
          </Panel>
          <Panel title="AI执行复盘">
            {recaps.length === 0 ? <div className="empty-state">今天暂无AI执行复盘，待老板确认的草稿不会自动落账。</div> : <div className="execution-recap-list compact">
              {recaps.map((recap) => <article className="execution-recap-card" key={recap.id}>
                <strong>{recap.summary}</strong>
                <p>{recap.intent_type || 'AI任务'} · {recap.status} · 风险：{recap.risk_level || '未标记'}</p>
                <button className="secondary-button" onClick={() => onNavigate(routeToPage(recap.route))}>查看任务</button>
              </article>)}
            </div>}
            <button className="secondary-button" onClick={() => onNavigate('execution-recaps')}>查看完整执行复盘</button>
          </Panel>
        </div>
        <aside className="daily-detail-side">
          <Panel title="下一步建议">
            <div className="report-next-actions vertical">
              {report.next_actions.map((action) => <button key={`${action.title}-${action.route}`} onClick={() => onNavigate(routeToPage(action.route))}>
                <b>{action.title}</b>
                <small>{action.reason}</small>
              </button>)}
            </div>
          </Panel>
          <Panel title="风险提醒">
            <div className="report-risk-notes detail">
              {report.risk_notes.map((note) => <p key={note}>□ {note}</p>)}
            </div>
          </Panel>
          <Panel title="日报时间线">
            <div className="daily-timeline">
              {timeline.map((item, index) => <button key={`${item.summary}-${index}`} onClick={() => onNavigate(routeToPage(item.route))}>
                <span>{item.time_label}</span>
                <strong>{item.actor_name}</strong>
                <small>{item.summary}</small>
              </button>)}
            </div>
          </Panel>
          <Panel title="近7天历史日报">
            <div className="daily-history-list">
              {history.length === 0 ? <div className="empty-state">暂无历史日报。</div> : history.map((item) => <article className="daily-history-item" key={item.report_date}>
                <div><strong>{item.report_date}</strong><small>{item.summary}</small></div>
                <span>{formatMoney(item.total_revenue)}元</span>
              </article>)}
            </div>
          </Panel>
        </aside>
      </div>
      <Panel title="证据来源">
        <div className="evidence-grid">
          {Object.entries(report.evidence || {}).map(([key, value]) => <span key={key}>{key}<b>{value}</b></span>)}
        </div>
      </Panel>
    </section>
  )
}

function ExecutionRecapsPage({ data, onNavigate }: { data: ExecutionRecapList; onNavigate: (page: Page) => void }) {
  const summary = data.summary
  return (
    <section className="execution-recaps-page">
      <div className="page-heading daily-detail-hero">
        <div>
          <span className="ai-badge">AI运营协调官</span>
          <h1>AI执行复盘</h1>
          <p>这里只展示已经由老板确认、并且真实落账的AI工作记录；待确认草稿不会出现在已完成列表。</p>
          <small>生成时间：{data.generated_at || '实时生成'}</small>
        </div>
        <div className="daily-health-orb healthy">
          <strong>{summary.total_count}</strong>
          <span>已完成任务</span>
        </div>
      </div>
      <div className="execution-summary-grid">
        <div><span>总复盘</span><b>{summary.total_count}</b></div>
        <div><span>销售</span><b>{summary.sales_order_count}</b></div>
        <div><span>采购</span><b>{summary.purchase_order_count}</b></div>
        <div><span>库存</span><b>{summary.inventory_count}</b></div>
      </div>
      {data.items.length === 0 ? <Panel title="暂无已完成AI工作"><div className="empty-state">AI生成的草稿必须经老板确认并落账后，才会进入执行复盘。</div></Panel> : <div className="execution-recap-list full">
        {data.items.map((item) => <article className="execution-recap-card detailed" key={item.confirmation_id}>
          <div className="recap-card-head"><span>{item.source_employee}</span><b>{item.kind}</b></div>
          <h3>{item.summary}</h3>
          <p>{item.intent_type || 'AI任务'} · {item.status} · 风险：{item.risk_level || '未标记'} · 完成：{item.resolved_at || item.created_at}</p>
          <div className="recap-effects">{item.effects.map((effect) => <span key={effect}>{effect}</span>)}</div>
          <div className="recap-evidence">{item.evidence.map((evidence) => <small key={evidence}>{evidence}</small>)}</div>
          <button className="secondary-button" onClick={() => onNavigate(routeToPage(item.next_route))}>查看相关业务</button>
        </article>)}
      </div>}
    </section>
  )
}

function KpiCard({ kpi, index }: { kpi: Overview['kpis'][number]; index: number }) {
  const icons = ['¥', '□', '◎', '☎']
  const tone = ['purple', 'blue', 'green', 'orange'][index % 4]
  return (
    <div className={`kpi-card ${tone}`}>
      <div>
        <span>{kpi.label}</span>
        <strong>{kpi.unit === '元' ? formatMoney(kpi.value) : kpi.value}</strong>
        <p><b>{kpi.trend_label || '保持稳定'}</b></p>
      </div>
      <i>{icons[index % icons.length]}</i>
    </div>
  )
}

function Panel({ title, action, children }: { title: string; action?: string; children: React.ReactNode }) {
  return <section className="panel"><div className="panel-header"><h3>{title}</h3>{action && <button>{action}</button>}</div>{children}</section>
}
function PriorityCard({ item }: { item: { title: string; reason: string; severity: string; evidence: string[] } }) { return <div className={`priority-card ${item.severity}`}><span className="todo-check">□</span><div><strong>{item.title}</strong><p>{item.reason}</p><small>{item.evidence.join(' / ')}</small></div></div> }
function EmployeeGrid({ employees }: { employees: AiEmployee[] }) {
  const avatars = ['◉','◇','▣','□','◎']
  return (
    <div className="employee-grid">
      {employees.map((e, index) => {
        const visibleMetrics = e.metrics.slice(0, 3)
        return (
          <div className={`employee-card tone-${index % 5} status-${e.status}`} key={e.key}>
            <div className="employee-avatar">{avatars[index % avatars.length]}</div>
            <b>{e.name}</b>
            <span>{e.description}</span>
            <em>{e.status_label || (e.status === 'working' ? '员工工作中' : e.status)}</em>
            <div className="employee-metrics">
              {visibleMetrics.map((metric) => (
                <small key={metric.label}>{metric.label}<strong>{metric.value}{metric.unit || ''}</strong></small>
              ))}
            </div>
            <p className="employee-last">最近：{e.last_activity_label || '暂无新任务'}</p>
            <button className="detail-button">{e.primary_action?.label || '查看详情'}</button>
          </div>
        )
      })}
    </div>
  )
}
function SuggestionList({ suggestions }: { suggestions: Suggestion[] }) { return <div className="stack-list">{suggestions.map((s, index) => <div className={`suggestion-card suggestion-${index % 3}`} key={s.id}><div className="suggestion-title"><i>{['↑','◇','✧'][index % 3]}</i><b>{s.title}</b></div><p>{s.summary}</p><small>依据：{s.evidence.join('；')}｜风险：{s.risk}</small><button>查看建议</button></div>)}</div> }
function ActivityList({ activities }: { activities: Activity[] }) { return <div className="timeline-list">{activities.map((a) => <div className="activity-row" key={a.id}><span>{a.time_label}</span><i></i><div><b>{a.actor_name}</b><p>{a.summary}，{a.impact}</p></div></div>)}</div> }

function SalesPage({ auth, stock, orders, customers, onChanged }: { auth: AuthState; stock: StockItem[]; orders: SalesOrder[]; customers: Customer[]; onChanged: () => void }) {
  const sellable = stock.find((item) => Number(item.current_quantity || 0) > 0)
  const canWriteSales = hasPermission(auth, 'sales:write')
  const canExportSales = hasPermission(auth, 'exports:sales')
  const [quantity, setQuantity] = useState('1')
  const [unitPrice, setUnitPrice] = useState('')
  const [customerName, setCustomerName] = useState('散客')
  const [customerId, setCustomerId] = useState('')
  const [selectedOrder, setSelectedOrder] = useState<SalesOrder | null>(null)
  const [returnQuantity, setReturnQuantity] = useState('1')
  const [operationMessage, setOperationMessage] = useState('')
  const selectedLine = selectedOrder?.items?.[0]

  async function createOrder() {
    if (!sellable) return
    const selectedCustomer = customers.find((customer) => customer.customer_id === customerId)
    const price = Number(unitPrice || sellable.current_price || 1)
    await api.createSalesOrder(auth, {
      customer_id: selectedCustomer?.customer_id,
      customer_name: selectedCustomer?.name || customerName,
      payment_method: 'cash',
      items: [{ inventory_item_id: sellable.inventory_item_id, quantity: Number(quantity || 1), unit_price: price }],
      note: 'PC/H5销售单'
    })
    setQuantity('1')
    setUnitPrice('')
    setOperationMessage('销售单已创建，库存与财务流水已同步更新。')
    onChanged()
  }

  async function openDetail(orderId: string) {
    const data = await api.getSalesOrder(auth, orderId)
    setSelectedOrder(data.order)
    setReturnQuantity('1')
    setOperationMessage('')
  }

  async function cancelOrder() {
    if (!selectedOrder) return
    if (!window.confirm('确认取消该销售单？取消后会回补库存并写入退款财务流水。')) return
    const data = await api.cancelSalesOrder(auth, selectedOrder.sales_order_id, 'PC/H5取消销售单')
    setSelectedOrder(data.order)
    setOperationMessage('销售单已取消，库存已回补，财务退款流水已生成。')
    onChanged()
  }

  async function returnOrder() {
    if (!selectedOrder || !selectedLine) return
    const data = await api.returnSalesOrder(auth, selectedOrder.sales_order_id, {
      items: [{ sales_order_line_id: selectedLine.sales_order_line_id, quantity: Number(returnQuantity || 1) }],
      reason: 'PC/H5退货退款'
    })
    setSelectedOrder(data.order)
    setOperationMessage('退货退款已完成，库存已回补，财务流水已更新。')
    onChanged()
  }

  return (
    <div className="content-grid">
      <section className="hero-card">
        <div>
          <div className="ai-badge">H1 已增强</div>
          <h1>销售单生命周期管理</h1>
          <p>支持创建销售单、查看详情、取消订单、退货退款，并联动库存回补与财务流水。</p>
        </div>
        <button className="primary-button" disabled={!canWriteSales || !sellable} title={canWriteSales ? '' : '需要销售写入权限'} onClick={() => void createOrder()}>创建销售单</button>
      </section>
      <Panel title="快速开销售单">
        <div className="inline-form">
          <select value={customerId} onChange={(e) => { setCustomerId(e.target.value); const customer = customers.find((c) => c.customer_id === e.target.value); if (customer) setCustomerName(customer.name) }}>
            <option value="">散客/手填客户</option>
            {customers.map((customer) => <option key={customer.customer_id} value={customer.customer_id}>{customer.name}</option>)}
          </select>
          <input value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="客户名称" />
          <input value={quantity} onChange={(e) => setQuantity(e.target.value)} placeholder="数量" />
          <input value={unitPrice} onChange={(e) => setUnitPrice(e.target.value)} placeholder={`单价，默认${sellable?.current_price || 1}`} />
        </div>
        <p className="helper-text">当前商品：{sellable ? `${sellable.item_name}，库存 ${sellable.current_quantity}${sellable.default_unit}` : '暂无可销售库存，请先入库。'}；选择客户后销售单会写入 customer_id，复购分析更准确。</p>
      </Panel>
      <Panel title="销售单列表">
        <div className="inline-form"><button className="secondary-button" disabled={!canExportSales} title={canExportSales ? '' : '需要销售导出权限'} onClick={() => void api.exportSalesOrders(auth)}>导出销售单CSV</button></div>
        <DataTable rows={orders} columns={['order_no','customer_name','total_amount','items_count','status']} action={(row) => <button className="secondary-button" onClick={() => void openDetail(String(row.sales_order_id))}>查看/处理</button>} />
      </Panel>
      {selectedOrder && <Panel title={`销售单详情：${selectedOrder.order_no}`}>
        <section className="detail-grid">
          <div><b>客户</b><p>{selectedOrder.customer_name || '散客'}</p></div>
          <div><b>状态</b><p>{selectedOrder.status}</p></div>
          <div><b>金额</b><p>{formatMoney(selectedOrder.total_amount)} 元</p></div>
          <div><b>备注</b><p>{selectedOrder.note || '-'}</p></div>
        </section>
        <DataTable rows={selectedOrder.items || []} columns={['item_name','quantity','unit','unit_price','line_amount']} />
        <div className="inline-form">
          <input value={returnQuantity} onChange={(e) => setReturnQuantity(e.target.value)} placeholder="退货数量" />
          <button className="secondary-button" disabled={!selectedLine || !['paid','partially_refunded'].includes(selectedOrder.status)} onClick={() => void returnOrder()}>退货/退款</button>
          <button className="danger-button" disabled={!['paid','partially_refunded'].includes(selectedOrder.status)} onClick={() => void cancelOrder()}>取消整单</button>
        </div>
        {operationMessage && <div className="assistant-reply">{operationMessage}</div>}
      </Panel>}
    </div>
  )
}

function PurchasingPage({ auth, stock, suppliers, purchaseOrders, onChanged }: { auth: AuthState; stock: StockItem[]; suppliers: Supplier[]; purchaseOrders: PurchaseOrder[]; onChanged: () => void }) {
  const firstStock = stock[0]
  const firstSupplier = suppliers[0]
  const [supplierName, setSupplierName] = useState('默认五金供应商')
  const [supplierPhone, setSupplierPhone] = useState('')
  const [quantity, setQuantity] = useState('5')
  const [unitCost, setUnitCost] = useState('10')
  const [selectedSupplierId, setSelectedSupplierId] = useState('')
  const activeSupplier = suppliers.find((supplier) => supplier.supplier_id === selectedSupplierId) || firstSupplier
  const canWritePurchasing = hasPermission(auth, 'purchasing:write')
  const canExportPurchasing = hasPermission(auth, 'exports:purchasing')
  const supplierOrders = activeSupplier ? purchaseOrders.filter((order) => order.supplier_id === activeSupplier.supplier_id) : []
  async function createSupplier() { if (!supplierName.trim()) return; await api.createSupplier(auth, { name: supplierName, phone: supplierPhone }); setSupplierName('默认五金供应商'); setSupplierPhone(''); onChanged() }
  async function createPurchase() { if (!activeSupplier || !firstStock) return; await api.createPurchaseOrder(auth, { supplier_id: activeSupplier.supplier_id, items: [{ inventory_item_id: firstStock.inventory_item_id, quantity: Number(quantity || 1), unit_cost: Number(unitCost || 0) }], note: 'PC/H5采购入库' }); onChanged() }
  return (
    <div className="content-grid">
      <section className="hero-card"><div><div className="ai-badge">H2 已增强</div><h1>采购/供应商闭环</h1><p>创建采购单会写入真实采购记录、自动入库，并生成采购支出财务流水；页面支持供应商采购记录聚合。</p></div><button className="primary-button" disabled={!canWritePurchasing || !activeSupplier || !firstStock} title={canWritePurchasing ? '' : '需要采购写入权限'} onClick={() => void createPurchase()}>创建采购入库单</button></section>
      <Panel title="新增供应商"><div className="inline-form"><input value={supplierName} onChange={(e) => setSupplierName(e.target.value)} placeholder="供应商名称" /><input value={supplierPhone} onChange={(e) => setSupplierPhone(e.target.value)} placeholder="联系电话" /><button className="primary-button" disabled={!canWritePurchasing} title={canWritePurchasing ? '' : '需要采购写入权限'} onClick={() => void createSupplier()}>新增供应商</button></div></Panel>
      <Panel title="快速采购入库"><div className="inline-form"><select value={activeSupplier?.supplier_id || ''} onChange={(e) => setSelectedSupplierId(e.target.value)}><option value="">选择供应商</option>{suppliers.map((supplier) => <option key={supplier.supplier_id} value={supplier.supplier_id}>{supplier.name}</option>)}</select><input value={quantity} onChange={(e) => setQuantity(e.target.value)} placeholder="采购数量" /><input value={unitCost} onChange={(e) => setUnitCost(e.target.value)} placeholder="采购单价" /></div><p className="helper-text">供应商：{activeSupplier?.name || '请先新增供应商'}；商品：{firstStock?.item_name || '暂无商品库存快照'}</p></Panel>
      <section className="kpi-grid"><div className="kpi-card"><span>供应商数量</span><strong>{suppliers.length}</strong><em>家</em><p>当前门店 active 供应商</p></div><div className="kpi-card"><span>采购单数量</span><strong>{purchaseOrders.length}</strong><em>单</em><p>当前门店采购记录</p></div><div className="kpi-card"><span>当前供应商采购</span><strong>{supplierOrders.length}</strong><em>单</em><p>{activeSupplier?.name || '未选择'}</p></div></section>
      <Panel title="供应商列表"><DataTable rows={suppliers} columns={['name','phone','status']} action={(row) => <button className="secondary-button" onClick={() => setSelectedSupplierId(String(row.supplier_id))}>查看采购记录</button>} /></Panel>
      <Panel title="当前供应商采购单"><DataTable rows={supplierOrders} columns={['order_no','status','total_amount','note','created_at']} /></Panel>
      <Panel title="全部采购单列表"><div className="inline-form"><button className="secondary-button" disabled={!canExportPurchasing} title={canExportPurchasing ? '' : '需要采购导出权限'} onClick={() => void api.exportPurchaseOrders(auth)}>导出采购单CSV</button></div><DataTable rows={purchaseOrders} columns={['order_no','status','total_amount','note','created_at']} /></Panel>
    </div>
  )
}

function CustomersPage({ auth, customers, orders, repurchase, onChanged }: { auth: AuthState; customers: Customer[]; orders: SalesOrder[]; repurchase: CustomerRepurchaseAnalysis | null; onChanged: () => void }) {
  const [name, setName] = useState('老王')
  const [phone, setPhone] = useState('')
  const [selectedCustomerId, setSelectedCustomerId] = useState('')
  const selectedCustomer = customers.find((customer) => customer.customer_id === selectedCustomerId) || customers[0]
  const canWriteCustomers = hasPermission(auth, 'customers:write')
  const selectedCustomerOrders = selectedCustomer ? orders.filter((order) => order.customer_id === selectedCustomer.customer_id || order.customer_name === selectedCustomer.name) : []
  async function createCustomer() { if (!name.trim()) return; await api.createCustomer(auth, { name, phone }); setName('老王'); setPhone(''); onChanged() }
  return (
    <div className="content-grid">
      <section className="hero-card"><div><div className="ai-badge">H2/H3 已增强</div><h1>客户档案与复购分析</h1><p>销售单已支持 customer_id 关联，复购分析优先按客户ID统计，避免同名客户误匹配。</p></div></section>
      <Panel title="新增客户"><div className="inline-form"><input value={name} onChange={(e) => setName(e.target.value)} placeholder="客户姓名" /><input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="联系电话" /><button className="primary-button" disabled={!canWriteCustomers} title={canWriteCustomers ? '' : '需要客户写入权限'} onClick={() => void createCustomer()}>新增客户</button></div></Panel>
      <section className="kpi-grid"><div className="kpi-card"><span>客户数量</span><strong>{repurchase?.summary.customer_count ?? customers.length}</strong><em>人</em><p>来自客户档案</p></div><div className="kpi-card"><span>匹配订单</span><strong>{repurchase?.summary.matched_order_count ?? 0}</strong><em>笔</em><p>优先按 customer_id 关联</p></div><div className="kpi-card"><span>当前客户订单</span><strong>{selectedCustomerOrders.length}</strong><em>笔</em><p>{selectedCustomer?.name || '未选择客户'}</p></div></section>
      <Panel title="客户列表"><DataTable rows={customers} columns={['name','phone','status']} action={(row) => <button className="secondary-button" onClick={() => setSelectedCustomerId(String(row.customer_id))}>查看购买记录</button>} /></Panel>
      <Panel title="当前客户购买记录"><p className="helper-text">客户：{selectedCustomer?.name || '暂无客户'}；销售单创建时选择客户后会自动关联 customer_id。</p><DataTable rows={selectedCustomerOrders} columns={['order_no','customer_name','total_amount','items_count','status']} /></Panel>
      <Panel title="复购分析"><DataTable rows={repurchase?.customers || []} columns={['name','phone','order_count','total_amount']} /></Panel>
    </div>
  )
}

function FinancePage({ auth, summary, transactions, onTransactionsChanged }: { auth: AuthState; summary: FinanceSummary | null; transactions: FinanceTransaction[]; onTransactionsChanged: (rows: FinanceTransaction[]) => void }) {
  if (!hasPermission(auth, 'finance:read')) return <AccessDenied title="财务流水需要财务或老板权限" message="店员账号不能查看收支汇总和财务流水，避免敏感经营数据泄露。" />
  const canExportFinance = hasPermission(auth, 'exports:finance')
  const [transactionType, setTransactionType] = useState('')
  const [direction, setDirection] = useState('')
  async function applyFilters() {
    const data = await api.listFinanceTransactions(auth, { transaction_type: transactionType || undefined, direction: direction || undefined })
    onTransactionsChanged(data.transactions)
  }
  return (
    <div className="content-grid">
      <section className="hero-card"><div><div className="ai-badge">H2 已增强</div><h1>财务流水/收支对账</h1><p>销售、退款、退货、采购都会沉淀为真实财务流水，并支持按流水类型和收支方向筛选。</p></div></section>
      <section className="kpi-grid"><div className="kpi-card"><span>总收入</span><strong>{formatMoney(summary?.total_income || 0)}</strong><em>元</em><p>销售收入</p></div><div className="kpi-card"><span>总支出</span><strong>{formatMoney(summary?.total_expense || 0)}</strong><em>元</em><p>采购/退款</p></div><div className="kpi-card"><span>净现金流</span><strong>{formatMoney(summary?.net_cashflow || 0)}</strong><em>元</em><p>收入 - 支出</p></div></section>
      <Panel title="流水筛选"><div className="inline-form"><select value={transactionType} onChange={(e) => setTransactionType(e.target.value)}><option value="">全部类型</option><option value="sales_revenue">销售收入</option><option value="sales_refund">销售退款</option><option value="purchase_payment">采购支出</option></select><select value={direction} onChange={(e) => setDirection(e.target.value)}><option value="">全部方向</option><option value="income">收入</option><option value="expense">支出</option></select><button className="secondary-button" onClick={() => void applyFilters()}>应用筛选</button><button className="secondary-button" disabled={!canExportFinance} title={canExportFinance ? '' : '需要财务导出权限'} onClick={() => void api.exportFinanceTransactions(auth)}>导出财务CSV</button></div></Panel>
      <Panel title="财务流水"><DataTable rows={transactions} columns={['transaction_type','direction','amount','source_type','counterparty_name','note']} /></Panel>
    </div>
  )
}

function ProductsPage({ auth, items, onChanged }: { auth: AuthState; items: InventoryItem[]; onChanged: () => void }) {
  const canWriteInventory = hasPermission(auth, 'inventory:write')
  const [name, setName] = useState('')
  const [sku, setSku] = useState('')
  async function create() { if (!name.trim()) return; await api.createItem(auth, { name, sku, default_unit: '个' }); setName(''); setSku(''); onChanged() }
  async function remove(id: string) { await api.deleteItem(auth, id); onChanged() }
  return <Panel title="商品管理"><div className="inline-form"><input placeholder="商品名称" value={name} onChange={(e) => setName(e.target.value)} /><input placeholder="SKU" value={sku} onChange={(e) => setSku(e.target.value)} /><button className="primary-button" disabled={!canWriteInventory} title={canWriteInventory ? '' : '需要库存写入权限'} onClick={() => void create()}>新增商品</button></div><DataTable rows={items} columns={['name','sku','default_unit','status']} action={(row) => <button className="danger-button" disabled={!canWriteInventory} title={canWriteInventory ? '' : '需要库存写入权限'} onClick={() => void remove(row.inventory_item_id)}>软删除</button>} /></Panel>
}

function InventoryPage({ auth, items, stock, events, onChanged }: { auth: AuthState; items: InventoryItem[]; stock: StockItem[]; events: LedgerEvent[]; onChanged: () => void }) {
  const canWriteInventory = hasPermission(auth, 'inventory:write')
  const canExportInventory = hasPermission(auth, 'exports:inventory')
  const firstItem = items[0]
  async function stockIn() { if (!firstItem) return; await api.stockIn(auth, { inventory_item_id: firstItem.inventory_item_id, quantity: 1, unit: firstItem.default_unit, price: 1, reason: 'PC/H5手动入库' }); onChanged() }
  async function stockOut() { if (!firstItem) return; await api.stockOut(auth, { inventory_item_id: firstItem.inventory_item_id, quantity: 1, unit: firstItem.default_unit, price: 1, reason: 'PC/H5手动出库' }); onChanged() }
  return <div className="content-grid"><Panel title="库存操作"><div className="inline-form"><button className="primary-button" disabled={!canWriteInventory || !firstItem} title={canWriteInventory ? '' : '需要库存写入权限'} onClick={() => void stockIn()}>对首个商品入库1</button><button className="secondary-button" disabled={!canWriteInventory || !firstItem} title={canWriteInventory ? '' : '需要库存写入权限'} onClick={() => void stockOut()}>对首个商品出库1</button><button className="secondary-button" disabled={!canExportInventory} title={canExportInventory ? '' : '需要库存导出权限'} onClick={() => void api.exportInventoryLedger(auth)}>导出库存流水CSV</button></div></Panel><Panel title="库存快照"><DataTable rows={stock} columns={['item_name','current_quantity','low_stock_threshold','default_unit']} /></Panel><Panel title="库存流水"><DataTable rows={events} columns={['item_name','event_type','quantity_delta','quantity_after','reason']} /></Panel></div>
}

function AiPage({ auth, overview, onChanged }: { auth: AuthState; overview: Overview | null; onChanged: () => void }) {
  const [message, setMessage] = useState('查一下今天销售额')
  const [draftMessage, setDraftMessage] = useState('卖出1把电动螺丝刀，单价99，客户老王')
  const [reply, setReply] = useState('')
  const [draftResult, setDraftResult] = useState('')
  async function send() { const data = await api.chat(auth, message); setReply(data.reply); onChanged() }
  async function createDraft() { const data = await api.createSalesOrderDraft(auth, draftMessage); setDraftResult(`已生成待确认销售单：${data.confirmation.confirmation_id}`); onChanged() }
  return <div className="content-grid"><section className="hero-card"><div><div className="ai-badge">AI运营协调官</div><h1>自然语言经营入口</h1><p>可查询营业数据、库存、热销排行；涉及业务写入时后端会生成待确认任务，审批后才落账。</p></div></section><Panel title="问AI运营协调官"><div className="chat-box"><textarea value={message} onChange={(e) => setMessage(e.target.value)} /><button className="primary-button" onClick={() => void send()}>发送</button>{reply && <div className="assistant-reply">{reply}</div>}</div></Panel><Panel title="AI生成销售单草稿"><div className="chat-box"><textarea value={draftMessage} onChange={(e) => setDraftMessage(e.target.value)} /><button className="primary-button" onClick={() => void createDraft()}>生成待确认销售单</button>{draftResult && <div className="assistant-reply">{draftResult}，请到任务中心审批。</div>}</div></Panel><Panel title="建议快捷入口"><SuggestionList suggestions={overview?.suggestions || []} /></Panel></div>
}

type TaskViewModel = {
  employee: string
  title: string
  impact: string
  risk: string
  confidence: string
  routeHint: string
  evidence: string[]
  summary: { label: string; value: string }[]
}

function buildTaskViewModel(confirmation: Confirmation): TaskViewModel {
  const payload = confirmation.draft_payload || {}
  const type = confirmation.confirmation_type
  if (type.includes('sales.order_create')) {
    const lines = Array.isArray(payload.items) ? payload.items as Record<string, unknown>[] : []
    const total = lines.reduce((sum, line) => sum + Number(line.line_amount || line.amount || 0), 0)
    const names = lines.map((line) => String(line.item_name || line.name || line.inventory_item_id || '商品')).join('、')
    return {
      employee: '销售分析员',
      title: '销售单草稿等待确认',
      impact: '确认后会创建销售单、扣减库存，并写入销售收入流水。',
      risk: '高风险：会改变库存和财务数据',
      confidence: lines.length ? '已解析商品明细' : '需要老板复核明细',
      routeHint: '销售单 / 库存 / 财务',
      evidence: [`识别到 ${lines.length || 1} 条销售明细`, names ? `商品：${names}` : '商品信息来自AI草稿', total > 0 ? `预计金额：${formatMoney(total)} 元` : '金额以草稿明细为准'],
      summary: [
        { label: '客户', value: String(payload.customer_name || payload.customer_id || '未填写') },
        { label: '明细数', value: String(lines.length || '-') },
        { label: '付款方式', value: String(payload.payment_method || '未填写') }
      ]
    }
  }
  if (type.includes('purchase.order_create')) {
    const lines = Array.isArray(payload.items) ? payload.items as Record<string, unknown>[] : []
    const total = lines.reduce((sum, line) => sum + Number(line.line_amount || 0), 0)
    const names = lines.map((line) => String(line.item_name || line.name || line.inventory_item_id || '商品')).join('、')
    return {
      employee: '采购专员',
      title: '采购入库草稿等待确认',
      impact: '确认后会创建采购单、增加库存，并写入采购支出流水。',
      risk: '高风险：会改变库存和财务数据',
      confidence: lines.length ? '已解析供应商和采购明细' : '需要老板复核采购明细',
      routeHint: '采购单 / 库存 / 财务',
      evidence: [`识别到 ${lines.length || 1} 条采购明细`, names ? `商品：${names}` : '商品信息来自AI草稿', total > 0 ? `预计支出：${formatMoney(total)} 元` : '金额以草稿明细为准'],
      summary: [
        { label: '供应商', value: String(payload.supplier_name || payload.supplier_id || '未填写') },
        { label: '明细数', value: String(lines.length || '-') },
        { label: '状态', value: '确认后入库' }
      ]
    }
  }
  if (type.includes('inventory.stock_in') || type === 'stock_in') {
    return {
      employee: '库存风控专员',
      title: '入库草稿等待确认',
      impact: '确认后会增加库存并写入库存流水。',
      risk: '中风险：会改变库存数量',
      confidence: '已生成入库草稿',
      routeHint: '库存管理',
      evidence: [`商品：${String(payload.item_name || payload.inventory_item_id || payload.item_id || '待确认')}`, `数量：${String(payload.quantity || payload.stock_in_quantity || '-')}`],
      summary: [
        { label: '单位', value: String(payload.unit || '-') },
        { label: '单价', value: String(payload.price || '-') },
        { label: '原因', value: String(payload.reason || 'AI生成草稿') }
      ]
    }
  }
  if (type.includes('inventory.stock_out') || type === 'stock_out') {
    return {
      employee: '库存风控专员',
      title: '出库草稿等待确认',
      impact: '确认后会扣减库存并写入库存流水。',
      risk: '高风险：会减少库存',
      confidence: '已生成出库草稿',
      routeHint: '库存管理',
      evidence: [`商品：${String(payload.item_name || payload.inventory_item_id || payload.item_id || '待确认')}`, `数量：${String(payload.quantity || payload.stock_out_quantity || '-')}`],
      summary: [
        { label: '单位', value: String(payload.unit || '-') },
        { label: '单价', value: String(payload.price || '-') },
        { label: '原因', value: String(payload.reason || 'AI生成草稿') }
      ]
    }
  }
  return {
    employee: 'AI运营协调官',
    title: 'AI任务草稿等待确认',
    impact: '确认后才会执行对应业务动作。',
    risk: '需复核：业务影响以草稿内容为准',
    confidence: '已生成待确认草稿',
    routeHint: '任务中心',
    evidence: [`类型：${type}`, `字段数：${Object.keys(payload).length}`],
    summary: Object.entries(payload).slice(0, 3).map(([label, value]) => ({ label, value: String(value ?? '-') }))
  }
}

function formatDateTime(value?: string) {
  if (!value) return '刚刚'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function TasksPage({ auth, confirmations, onChanged }: { auth: AuthState; confirmations: Confirmation[]; onChanged: () => void }) {
  const [executionRecaps, setExecutionRecaps] = useState<Confirmation[]>([])
  const canApprove = hasPermission(auth, 'confirmations:approve')
  const [busyId, setBusyId] = useState<string | null>(null)
  async function approve(id: string) {
    setBusyId(id)
    try {
      const approved = await api.approveConfirmation(auth, id)
      setExecutionRecaps((items) => [approved, ...items.filter((item) => item.confirmation_id !== id)].slice(0, 5))
      onChanged()
    } finally {
      setBusyId(null)
    }
  }
  async function reject(id: string) { await api.rejectConfirmation(auth, id); onChanged() }
  return (
    <div className="content-grid">
      <section className="hero-card task-hero">
        <div>
          <div className="ai-badge">AI Task Flow</div>
          <h1>AI任务中心</h1>
          <p>每个高风险经营动作都会先进入任务流：AI理解与生成草稿，但必须老板确认后才落账。确认后会生成执行复盘。</p>
        </div>
        <div className="task-hero-count"><span>{confirmations.length}</span><small>待确认任务</small></div>
      </section>
      {executionRecaps.length > 0 && <Panel title="刚刚完成的AI执行复盘">
        <div className="execution-recap-list">
          {executionRecaps.map((confirmation) => <ExecutionRecapCard key={confirmation.confirmation_id} confirmation={confirmation} />)}
        </div>
      </Panel>}
      <Panel title="等待老板确认的AI任务">
        {confirmations.length === 0 ? <Empty text="暂无待确认AI任务。你可以在首页 Command Center 里生成销售草稿来体验完整任务流。" /> : <div className="task-flow-list">
          {confirmations.map((confirmation) => {
            const vm = buildTaskViewModel(confirmation)
            return <article className="task-flow-card" key={confirmation.confirmation_id}>
              <div className="task-flow-head">
                <div><span className="task-employee">{vm.employee}</span><h3>{vm.title}</h3><p>{vm.impact}</p></div>
                <div className="task-status-pill">等待确认</div>
              </div>
              <div className="task-stage-rail" aria-label="AI任务阶段">
                {['已发现', '已分析', '已生成草稿', '等待老板确认'].map((stage) => <span key={stage}>{stage}</span>)}
              </div>
              <div className="task-info-grid">
                <div className="task-info-box"><small>风险边界</small><b>{vm.risk}</b></div>
                <div className="task-info-box"><small>AI判断</small><b>{vm.confidence}</b></div>
                <div className="task-info-box"><small>影响模块</small><b>{vm.routeHint}</b></div>
                <div className="task-info-box"><small>创建时间</small><b>{formatDateTime(confirmation.created_at)}</b></div>
              </div>
              <div className="task-evidence"><strong>AI依据</strong>{vm.evidence.map((item) => <span key={item}>{item}</span>)}</div>
              <div className="task-summary-grid">{vm.summary.map((item) => <div key={item.label}><small>{item.label}</small><b>{item.value}</b></div>)}</div>
              <details className="task-raw-payload"><summary>查看原始草稿数据</summary><pre>{JSON.stringify(confirmation.draft_payload, null, 2)}</pre></details>
              <div className="task-actions">
                <button className="primary-button" disabled={!canApprove || busyId === confirmation.confirmation_id} title={canApprove ? '' : '需要老板审批权限'} onClick={() => void approve(confirmation.confirmation_id)}>{busyId === confirmation.confirmation_id ? '执行中...' : '确认并执行'}</button>
                <button className="secondary-button" disabled={!canApprove || busyId === confirmation.confirmation_id} title={canApprove ? '' : '需要老板审批权限'} onClick={() => void reject(confirmation.confirmation_id)}>拒绝任务</button>
                <span>任务ID：{confirmation.confirmation_id}</span>
              </div>
            </article>
          })}
        </div>}
      </Panel>
    </div>
  )
}

type ExecutionResult = {
  status?: string
  entity_type?: string
  entity_id?: string
  summary?: string
  effects?: Record<string, string>
  next_route?: string
}

function getExecutionResult(confirmation: Confirmation): ExecutionResult | null {
  const result = confirmation.resolution_payload?.execution_result
  if (!result || typeof result !== 'object' || Array.isArray(result)) return null
  return result as ExecutionResult
}

function ExecutionRecapCard({ confirmation }: { confirmation: Confirmation }) {
  const result = getExecutionResult(confirmation)
  if (!result) return null
  return <article className="execution-recap-card">
    <div className="execution-recap-head">
      <span>执行复盘</span>
      <b>{result.summary || 'AI任务已执行完成'}</b>
    </div>
    <div className="execution-effect-grid">
      {Object.entries(result.effects || {}).map(([key, value]) => <div key={key}><small>{key}</small><strong>{value}</strong></div>)}
    </div>
    <div className="execution-meta">
      <span>业务对象：{result.entity_type || '-'} / {result.entity_id || '-'}</span>
      <span>确认ID：{confirmation.confirmation_id}</span>
    </div>
  </article>
}


type AcceptanceStatus = 'passed' | 'trial' | 'before-production'
type AcceptanceItem = {
  title: string
  owner: string
  status: AcceptanceStatus
  summary: string
  evidence: string[]
  route: Page
}

function acceptanceStatusLabel(status: AcceptanceStatus) {
  if (status === 'passed') return '已通过'
  if (status === 'trial') return '可试运行'
  return '生产前补强'
}

function CommercialTrialAcceptancePage({ overview, items, stock, events, orders, suppliers, purchaseOrders, customers, financeTransactions, financeSummary, confirmations, executionRecapList, onNavigate }: {
  overview: Overview
  items: InventoryItem[]
  stock: StockItem[]
  events: LedgerEvent[]
  orders: SalesOrder[]
  suppliers: Supplier[]
  purchaseOrders: PurchaseOrder[]
  customers: Customer[]
  financeTransactions: FinanceTransaction[]
  financeSummary: FinanceSummary | null
  confirmations: Confirmation[]
  executionRecapList: ExecutionRecapList | null
  onNavigate: (page: Page) => void
}) {
  const businessItems: AcceptanceItem[] = [
    { title: '登录与门店上下文', owner: '系统管理员', status: 'passed', summary: '手机号演示登录、租户与门店上下文选择已接入真实后端。', evidence: [`当前门店：${overview.store.shop_name}`, `租户：${overview.store.tenant_name || overview.store.tenant_id}`], route: 'dashboard' },
    { title: '商品管理', owner: '商品档案员', status: 'trial', summary: '商品新增、列表、软删除已可用，历史账本不被物理删除破坏。', evidence: [`商品数：${items.length}`, '删除采用软删除边界'], route: 'products' },
    { title: '库存账本与快照', owner: '库存守护员', status: 'trial', summary: '库存入库/出库写不可变 ledger，并投影到当前库存快照。', evidence: [`库存快照：${stock.length}`, `库存流水：${events.length}`], route: 'inventory' },
    { title: '销售单闭环', owner: '销售分析员', status: 'trial', summary: '销售单创建后同步扣减库存，并写入销售收入财务流水。', evidence: [`销售单：${orders.length}`, `今日收入：${formatMoney(financeSummary?.total_income || 0)}元`], route: 'sales' },
    { title: '采购单闭环', owner: '进货专员', status: 'trial', summary: '采购单创建后同步入库，并写入采购支出财务流水。', evidence: [`供应商：${suppliers.length}`, `采购单：${purchaseOrders.length}`], route: 'purchasing' },
    { title: '客户复购分析', owner: '客户运营员', status: 'trial', summary: '客户档案与销售单关联，可形成基础复购分析。', evidence: [`客户：${customers.length}`, '按当前门店数据聚合'], route: 'customers' },
    { title: '财务流水', owner: '营业数据员', status: 'trial', summary: '销售收入、采购支出、退款等财务流水使用真实后端数据。', evidence: [`流水：${financeTransactions.length}`, `净现金流：${formatMoney(financeSummary?.net_cashflow || 0)}元`], route: 'finance' }
  ]
  const aiItems: AcceptanceItem[] = [
    { title: 'AI Command Center', owner: 'AI运营协调官', status: 'passed', summary: '首页自然语言入口可识别经营查询、销售/采购/库存草稿等意图。', evidence: ['经营查询只读', '写操作进入待确认任务'], route: 'dashboard' },
    { title: 'AI草稿生成', owner: '销售分析员 / 进货专员 / 库存守护员', status: 'passed', summary: '销售、采购、库存类自然语言写操作均先生成 pending confirmation。', evidence: ['confirmation-first', `待确认：${confirmations.length}`], route: 'tasks' },
    { title: '任务中心审批', owner: '老板', status: 'passed', summary: '老板确认后才落账，审批成功后生成 execution_result 复盘。', evidence: ['不自动审批', '审批后才改库存/销售/采购/财务'], route: 'tasks' },
    { title: '真实通知中心', owner: 'AI参谋', status: 'passed', summary: '通知聚合真实待确认任务、库存风险和经营日报建议。', evidence: [`待关注：${overview.notifications.attention_count || 0}`, `未读：${overview.notifications.unread_count || 0}`], route: 'dashboard' },
    { title: 'AI经营日报', owner: 'AI参谋', status: 'passed', summary: '日报由 BFF 聚合真实销售、库存、任务和风险证据生成。', evidence: [overview.daily_advisor_report?.summary || '日报已接入', `建议数：${overview.daily_advisor_report?.suggestion_count || 0}`], route: 'daily-report' },
    { title: 'AI执行复盘', owner: 'AI运营协调官', status: 'passed', summary: '仅展示已审批且真实落账的 AI 工作结果，不把 pending 当完成。', evidence: [`已完成复盘：${executionRecapList?.summary.total_count || 0}`, '来自 confirmation.resolution_payload.execution_result'], route: 'execution-recaps' }
  ]
  const hardeningItems: AcceptanceItem[] = [
    { title: '多租户/门店隔离', owner: '平台安全', status: 'passed', summary: '核心业务查询按 tenant_id + shop_id 限定，跨租户资源统一隐藏。', evidence: ['tenant/shop context token', '商品详情/修改/删除跨租户统一 404'], route: 'dashboard' },
    { title: '关键操作审计', owner: '平台安全', status: 'passed', summary: '销售、采购、客户、导出等关键动作写入 V2AuditLog。', evidence: ['审计动作覆盖核心商业操作', '导出行为也写审计'], route: 'inventory' },
    { title: 'CSV导出', owner: '营业数据员', status: 'passed', summary: '销售单、采购单、财务流水、库存流水由后端真实数据导出，并按角色权限分级保护。', evidence: ['四类CSV导出接口', '受 tenant/shop 隔离与 RBAC 约束'], route: 'finance' },
    { title: 'RBAC权限角色', owner: '平台安全', status: 'passed', summary: '已补齐 owner/clerk/finance 基础商用角色，关键写入、审批、财务与导出均由后端强制校验。', evidence: ['K1 已完成', '无权限返回 403 permission_denied'], route: 'dashboard' },
    { title: 'request_id错误追踪', owner: '平台运维', status: 'passed', summary: '未处理异常返回并记录 X-Request-ID，便于定位问题。', evidence: ['统一错误结构', '不泄露敏感信息'], route: 'dashboard' },
    { title: '结构化日志', owner: '平台运维', status: 'passed', summary: '请求链路日志已包含 request_id、path、status_code、latency_ms 等结构化字段，支持线上排障。', evidence: ['K4 已完成', 'token/password/secret 自动脱敏'], route: 'dashboard' },
    { title: '告警预留', owner: '平台运维', status: 'passed', summary: '已预留 webhook 告警配置与 readiness 状态，默认 mock，不输出 webhook URL。', evidence: ['APP_ALERT_WEBHOOK_ENABLED', 'webhook URL 只显示是否配置'], route: 'dashboard' },
    { title: 'Docker 8001部署', owner: '平台运维', status: 'passed', summary: 'FastAPI 与 H5 静态资源已通过 business-backend 容器提供服务。', evidence: ['0.0.0.0:8001', '/api/v2/health 正常'], route: 'dashboard' },
    { title: 'readiness/preflight', owner: '平台运维', status: 'passed', summary: '默认 preflight、Docker 验收、Provider安全边界、生产配置、Redis限流、结构化日志与告警预留已纳入试运行门禁。', evidence: ['K2/K3 生产预检', 'K4 observability/alerting 预检'], route: 'dashboard' },
    { title: 'PostgreSQL生产配置', owner: '平台运维', status: 'passed', summary: 'APP_ENV=production 时 readiness 会要求 PostgreSQL-compatible DATABASE_URL，SQLite 不会被误判为正式生产 ready。', evidence: ['不输出数据库连接串', 'SQLite 仅适合本地演示/试运行'], route: 'dashboard' },
    { title: 'Redis限流', owner: '平台运维', status: 'passed', summary: '限流后端已支持 memory/redis；APP_ENV=production 且启用限流时 readiness 要求 Redis-backed backend。', evidence: ['K3 已完成', '不输出 REDIS_URL/密码'], route: 'dashboard' },
    { title: 'Provider trial安全边界', owner: 'AI平台', status: 'before-production', summary: '真实 Provider 小流量试运行必须显式 opt-in，默认不读取凭证、不访问真实 Provider。', evidence: ['RUN_PROVIDER_TRIAL_PREFLIGHT=0 默认关闭', 'API key/token 不输出'], route: 'ai' },
    { title: '生产前补强', owner: '平台负责人', status: 'before-production', summary: '正式商用前建议继续补齐异步导出、HTTPS/域名、真实短信。', evidence: ['RBAC、生产预检、Redis限流、结构化日志告警基础已完成', '生产规模化仍需补强'], route: 'coming-soon' }
  ]
  const allItems = [...businessItems, ...aiItems, ...hardeningItems]
  const passedCount = allItems.filter((item) => item.status === 'passed' || item.status === 'trial').length
  const hardeningCount = allItems.filter((item) => item.status === 'before-production').length
  const aiNativeCount = aiItems.length
  return (
    <section className="trial-acceptance-page">
      <div className="page-heading trial-acceptance-hero">
        <div>
          <span className="ai-badge">Commercial Trial Gate</span>
          <h1>商用试运行验收清单</h1>
          <p>把当前 Business 的真实能力、AI-native 闭环、商用硬化和生产前差距放在一张清单里。这里只展示能力状态与真实计数，不伪造订单、客户或财务结果。</p>
          <small>当前分支：hermes/ai-native-saas-rewrite · 服务：business-backend:8001</small>
        </div>
        <div className="trial-readiness-orb">
          <strong>可试运行</strong>
          <span>正式商用前继续补强</span>
        </div>
      </div>
      <div className="trial-summary-grid">
        <div><span>可试运行能力</span><b>{passedCount}</b><small>已通过/可试运行</small></div>
        <div><span>AI-native闭环</span><b>{aiNativeCount}</b><small>自然语言→确认→落账→复盘</small></div>
        <div><span>生产前补强</span><b>{hardeningCount}</b><small>正式商用前继续做</small></div>
        <div><span>部署状态</span><b>8001</b><small>Docker H5 + API</small></div>
      </div>
      <AcceptanceSection title="核心业务闭环" description="老板日常经营必须能走通的真实业务链路。" items={businessItems} onNavigate={onNavigate} />
      <AcceptanceSection title="AI-native闭环" description="从自然语言到AI员工分工、待确认任务、老板审批、真实落账、执行复盘。" items={aiItems} onNavigate={onNavigate} />
      <AcceptanceSection title="商用硬化与部署" description="试运行必须具备的隔离、审计、导出、错误追踪、部署和安全边界。" items={hardeningItems} onNavigate={onNavigate} />
      <Panel title="J6 验收结论">
        <div className="trial-conclusion">
          <p><b>当前判断：</b>Business 已具备商用试运行入口，可以给老板按引导流程试用；但正式规模化商用前仍建议完成异步导出、HTTPS/域名、真实短信验证码等 Phase K 补强。</p>
          <button className="primary-button" onClick={() => onNavigate('dashboard')}>回到AI工作台</button>
          <button className="secondary-button" onClick={() => onNavigate('tasks')}>查看待确认任务</button>
          <button className="secondary-button" onClick={() => onNavigate('execution-recaps')}>查看AI执行复盘</button>
        </div>
      </Panel>
    </section>
  )
}

function AcceptanceSection({ title, description, items, onNavigate }: { title: string; description: string; items: AcceptanceItem[]; onNavigate: (page: Page) => void }) {
  return (
    <Panel title={title}>
      <p className="trial-section-description">{description}</p>
      <div className="acceptance-card-grid">
        {items.map((item) => <article className={`acceptance-card status-${item.status}`} key={item.title}>
          <div className="acceptance-card-head">
            <span>{item.owner}</span>
            <b>{acceptanceStatusLabel(item.status)}</b>
          </div>
          <h3>{item.title}</h3>
          <p>{item.summary}</p>
          <div className="acceptance-evidence">
            {item.evidence.map((line) => <small key={line}>{line}</small>)}
          </div>
          <button className="secondary-button" onClick={() => onNavigate(item.route)}>查看对应模块</button>
        </article>)}
      </div>
    </Panel>
  )
}

const moduleRoadmap = [
  { name: '销售单/订单', phase: 'F1', value: '让今日销售额、销售笔数、库存出库形成完整交易闭环。', status: '已开放' },
  { name: '采购/供应商', phase: 'F2', value: '把低库存预警升级为采购建议、采购单和收货入库。', status: '已开放' },
  { name: '客户档案', phase: 'F3', value: '支持客户建档和复购分析。', status: '已开放' },
  { name: '财务流水', phase: 'F4', value: '沉淀现金流、收入支出和对账汇总能力。', status: '已开放' },
  { name: '营销/售后', phase: 'F5', value: '基于真实订单和客户数据生成营销建议与售后闭环。', status: '后续开放' }
]

function ComingSoon() {
  return <div className="content-grid"><section className="hero-card"><div><div className="ai-badge">商业能力路线</div><h1>未完成模块只展示边界，不展示假数据</h1><p>当前商用试运行已开放销售、采购、客户、财务与AI确认审批闭环。营销/售后仍按真实后端领域模型逐步开放。</p></div></section><Panel title="下一阶段模块路线"> <div className="roadmap-grid">{moduleRoadmap.map((m) => <div className="roadmap-card" key={m.phase}><span>{m.phase}</span><b>{m.name}</b><p>{m.value}</p><em>{m.status}</em></div>)}</div></Panel></div>
}
function Empty({ text }: { text: string }) { return <div className="empty-state">{text}</div> }
function SkeletonHome() { return <div className="skeleton"><span /><span /><span /></div> }

function DataTable<T extends Record<string, unknown>>({ rows, columns, action }: { rows: T[]; columns: string[]; action?: (row: T) => React.ReactNode }) {
  if (!rows.length) return <Empty text="暂无数据，完成业务操作后这里会自动更新。" />
  return <div className="table-wrap"><table><thead><tr>{columns.map((c) => <th key={c}>{c}</th>)}{action && <th>操作</th>}</tr></thead><tbody>{rows.map((row, index) => <tr key={String(row.id || row.sales_order_id || row.inventory_item_id || row.event_id || index)}>{columns.map((c) => <td key={c}>{String(row[c] ?? '-')}</td>)}{action && <td>{action(row)}</td>}</tr>)}</tbody></table></div>
}

export default App
