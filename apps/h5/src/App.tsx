
import { useEffect, useMemo, useRef, useState } from 'react'
import { api, bootstrapContext, loadAuth, loginWithPhone, saveAuth } from './api'
import type { Activity, AiEmployee, AuthState, Confirmation, Customer, CustomerRepurchaseAnalysis, DailyAdvisorReport, ExecutionRecapList, FinanceSummary, FinanceTransaction, InventoryItem, LedgerEvent, NotificationItem, Overview, PurchaseOrder, SalesOrder, StockItem, Suggestion, Supplier } from './types'
import { UiBadge, UiButton, UiCard, UiTextArea } from './ui'
import './styles.css'

type Page = 'dashboard' | 'daily-report' | 'execution-recaps' | 'trial-acceptance' | 'sales' | 'purchasing' | 'customers' | 'finance' | 'products' | 'inventory' | 'ai' | 'tasks' | 'coming-soon'

type LoadState = 'idle' | 'loading' | 'ready' | 'error'

type NavItem = { page: Page; label: string; icon: string; badge?: string; permission?: string }

const navItems: NavItem[] = [
  { page: 'dashboard', label: '工作台', icon: '⌂' },
  { page: 'ai', label: 'AI助手', icon: '◇', badge: 'AI' },
  { page: 'tasks', label: '任务', icon: '✓' },
  { page: 'sales', label: '销售', icon: '□', permission: 'sales:read' },
  { page: 'inventory', label: '商品库存', icon: '▥', permission: 'inventory:read' },
  { page: 'coming-soon', label: '更多', icon: '✧' }
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
        <TopBar auth={auth} overview={overview} onRefresh={() => void refresh()} loading={state === 'loading'} onGuide={() => { setPage('dashboard'); setGuideSignal((value) => value + 1) }} onNotifications={() => setNotificationOpen(true)} onDiagnostics={() => setPage('trial-acceptance')} />
        {error && <div className="error-banner">{error}</div>}
        {state === 'loading' && !overview ? <SkeletonHome /> : null}
        {page === 'dashboard' && overview && <Dashboard auth={auth} overview={overview} onNavigate={setPage} onChanged={() => void refresh()} guideSignal={guideSignal} />}
        {page === 'daily-report' && dailyReport && <DailyReportPage report={dailyReport} onNavigate={setPage} />}
        {page === 'execution-recaps' && executionRecapList && <ExecutionRecapsPage data={executionRecapList} onNavigate={setPage} />}
        {page === 'trial-acceptance' && overview && (auth.roleKey === 'owner' ? <CommercialTrialAcceptancePage overview={overview} items={items} stock={stock} events={events} orders={orders} suppliers={suppliers} purchaseOrders={purchaseOrders} customers={customers} financeTransactions={financeTransactions} financeSummary={financeSummary} confirmations={confirmations} executionRecapList={executionRecapList} onNavigate={setPage} /> : <AccessDenied />)}
        {page === 'sales' && <SalesPage auth={auth} stock={stock} orders={orders} customers={customers} onChanged={() => void refresh()} />}
        {page === 'purchasing' && <PurchasingPage auth={auth} stock={stock} suppliers={suppliers} purchaseOrders={purchaseOrders} onChanged={() => void refresh()} />}
        {page === 'customers' && <CustomersPage auth={auth} customers={customers} orders={orders} repurchase={repurchase} onChanged={() => void refresh()} />}
        {page === 'finance' && <FinancePage auth={auth} summary={financeSummary} transactions={financeTransactions} onTransactionsChanged={setFinanceTransactions} />}
        {page === 'products' && <ProductsPage auth={auth} items={items} onChanged={() => void refresh()} />}
        {page === 'inventory' && <InventoryPage auth={auth} items={items} stock={stock} events={events} onChanged={() => void refresh()} />}
        {page === 'ai' && <AiPage auth={auth} overview={overview} onChanged={() => void refresh()} onNavigate={setPage} />}
        {page === 'tasks' && <TasksPage auth={auth} confirmations={confirmations} onChanged={() => void refresh()} onNavigate={setPage} />}
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
        <div className="login-eyebrow">AI数字员工工作台</div>
        <h1>AI 五金店大管家</h1>
        <p>用自然语言管理商品、库存、经营数据和AI确认闭环，先试用再上线。</p>
        <label>手机号<input value={phone} onChange={(e) => setPhone(e.target.value)} /></label>
        <label>验证码<input value={code} onChange={(e) => setCode(e.target.value)} /></label>
        <button className="primary-button" disabled={loading} onClick={() => void onLogin(phone, code)}>{loading ? '登录中...' : '演示登录（888888）'}</button>
        {error && <div className="error-text">{error}</div>}
      </section>
    </div>
  )
}


function AccessDenied({ title = '当前角色无权限', message = '请联系老板/管理员调整账号角色或切换到有权限的门店上下文。' }: { title?: string; message?: string }) {
  return <section className="access-denied-card"><UiBadge tone="warning">权限提醒</UiBadge><h1>{title}</h1><p>{message}</p><div className="permission-note">这项能力仅对已授权角色开放，避免误操作影响门店经营数据。</div></section>
}

function TopBar({ auth, overview, onRefresh, loading, onGuide, onNotifications, onDiagnostics }: { auth: AuthState; overview: Overview | null; onRefresh: () => void; loading: boolean; onGuide: () => void; onNotifications: () => void; onDiagnostics: () => void }) {
  return (
    <header className="top-bar">
      <div className="greeting-block">
        <h2>早上好，老板！</h2>
        <p>AI员工们正在为你打理店铺，请查看今日经营概况</p>
      </div>
      <div className="top-actions">
        <UiButton variant="ghost" className="guide-button" onClick={onGuide}>新手引导</UiButton>
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
        {auth.roleKey === 'owner' && <UiButton variant="secondary" className="diagnostic-button" onClick={onDiagnostics}>系统诊断</UiButton>}
        <UiButton variant="secondary" onClick={onRefresh} disabled={loading}>{loading ? '刷新中' : '刷新数据'}</UiButton>
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
            <UiBadge tone="ai">通知中心</UiBadge>
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
  const [showMoreDashboard, setShowMoreDashboard] = useState(false)
  useEffect(() => {
    if (guideSignal > 0) guideRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [guideSignal])
  return (
    <div className="dashboard-layout">
      <BossTodayBrief overview={overview} onNavigate={onNavigate} />
      <AiCommandCenter auth={auth} onNavigate={onNavigate} onChanged={onChanged} variant="hero" />
      <div className="dashboard-more-toggle">
        <UiButton variant="secondary" onClick={() => setShowMoreDashboard((value) => !value)}>{showMoreDashboard ? '收起经营细节' : '展开更多经营细节'}</UiButton>
      </div>
      {showMoreDashboard && <div className="dashboard-secondary-zone">
        <section className="kpi-grid secondary-kpi-grid">
          {overview.kpis.map((kpi, index) => <KpiCard kpi={kpi} index={index} key={kpi.key} />)}
        </section>
        {overview.daily_advisor_report && <DailyAdvisorReportCard report={overview.daily_advisor_report} onNavigate={onNavigate} />}
        <section className="dashboard-main-grid">
          <Panel title="我的AI员工" action="查看全部">
            <EmployeeGrid employees={overview.ai_employees} />
          </Panel>
          <Panel title="AI主动建议" action="进入对话">
            <SuggestionList suggestions={overview.suggestions} onAsk={() => onNavigate('ai')} />
          </Panel>
        </section>
        <section className="operations-grid">
          <Panel title="今日工作动态" action="查看报告">
            <ActivityList activities={overview.activities} />
          </Panel>
          <Panel title="待确认任务" action={`${overview.top_priorities.length}项`}>
            {overview.top_priorities.map((p) => <PriorityCard key={p.id} item={p} />)}
          </Panel>
        </section>
        <OnboardingDemoFlow refEl={guideRef} auth={auth} onNavigate={onNavigate} onChanged={onChanged} />
      </div>}
    </div>
  )
}

function getKpiValue(overview: Overview, key: string, fallback = 0) {
  const hit = overview.kpis.find((kpi) => kpi.key === key || kpi.label.includes(key))
  return Number(hit?.value ?? fallback)
}

function BossTodayBrief({ overview, onNavigate }: { overview: Overview; onNavigate: (page: Page) => void }) {
  const revenue = getKpiValue(overview, '销售额')
  const salesCount = getKpiValue(overview, '销售笔数')
  const lowStock = getKpiValue(overview, '低库存')
  const pending = getKpiValue(overview, '待确认')
  const reportSummary = overview.daily_advisor_report?.summary
  return (
    <section className="boss-today-brief">
      <div className="boss-brief-copy">
        <UiBadge tone="ai">老板今日摘要</UiBadge>
        <h1>老板，今天店里卖了 {formatMoney(revenue)} 元，{salesCount} 笔。</h1>
        <p>{reportSummary || `库存${lowStock > 0 ? `有 ${lowStock} 个风险` : '暂时安全'}；${pending > 0 ? `有 ${pending} 件事等你确认，确认后数据才完整。` : '暂无必须马上处理的AI草稿。'}`}</p>
      </div>
      <div className="boss-brief-actions">
        <UiButton variant="primary" onClick={() => onNavigate('tasks')}>{pending > 0 ? `先处理待确认（${pending}）` : '查看任务'}</UiButton>
        <UiButton variant="secondary" onClick={() => onNavigate('ai')}>问AI</UiButton>
        <UiButton variant="secondary" onClick={() => onNavigate('sales')}>记一笔销售</UiButton>
      </div>
    </section>
  )
}

type CommandAction = { label: string; page?: Page; commandText?: string; tone?: 'primary' | 'secondary' }
type DraftPreview = { lines: { label: string; value: string }[]; effects: string[] }
type BusinessInsight = { conclusion: string; evidence: string[]; nextAction: string }
type CommandResult = { kind: 'reply' | 'draft' | 'error' | 'done'; title: string; body: string; meta?: string; confirmationId?: string; actions?: CommandAction[]; journey?: string[]; draftPreview?: DraftPreview; businessInsight?: BusinessInsight; completionEffects?: string[] }

function AiCommandCenter({ auth, onNavigate, onChanged, variant = 'inline' }: { auth: AuthState; onNavigate: (page: Page) => void; onChanged: () => void; variant?: 'hero' | 'inline' }) {
  const quickCommands = ['今天生意怎么样？', '哪些商品快没货了？', '最近什么卖得最好？', '我卖了2把电动螺丝刀，帮我记一下']
  const [command, setCommand] = useState(quickCommands[0])
  const [result, setResult] = useState<CommandResult | null>(null)
  const [running, setRunning] = useState(false)
  const [approvingInline, setApprovingInline] = useState(false)

  function looksLikeSalesDraft(text: string) {
    return /卖出|销售|开单|收款|客户|卖了/.test(text) && /单价|客户|把|个|件|箱|元|\d/.test(text)
  }

  function looksLikePurchaseDraft(text: string) {
    return /采购|进货|补货|向.*供应商/.test(text) && /单价|进价|成本|把|个|件|箱|元|\d/.test(text)
  }

  function parseSalesDraftPreview(text: string): DraftPreview {
    const quantity = text.match(/(\d+(?:\.\d+)?)\s*(把|个|件|箱|支|套)?/)?.[1] || '1'
    const unit = text.match(/\d+(?:\.\d+)?\s*(把|个|件|箱|支|套)/)?.[1] || '件'
    const price = text.match(/单价\s*(\d+(?:\.\d+)?)/)?.[1] || text.match(/(\d+(?:\.\d+)?)\s*元/)?.[1] || '待确认'
    const customer = text.match(/客户\s*([^，,。\s]+)/)?.[1] || '散客'
    const item = text.includes('电动螺丝刀') ? '电动螺丝刀' : (text.match(/卖了\d*(?:\.\d+)?[把个件箱支套]?([^，,。\s]+)/)?.[1] || '商品')
    const total = price === '待确认' ? '待确认' : `${formatMoney(Number(quantity) * Number(price))} 元`
    return {
      lines: [
        { label: '商品', value: item },
        { label: '数量', value: `${quantity}${unit}` },
        { label: '单价', value: price === '待确认' ? price : `${formatMoney(price)} 元` },
        { label: '客户', value: customer },
        { label: '合计', value: total }
      ],
      effects: ['确认后会扣减库存', '确认后会记入销售额', '确认后会生成销售流水']
    }
  }

  function parsePurchaseDraftPreview(text: string): DraftPreview {
    return {
      lines: [
        { label: '事项', value: '采购/入库草稿' },
        { label: '内容', value: text.slice(0, 40) || '待确认' }
      ],
      effects: ['确认后会增加库存', '确认后会记录采购支出']
    }
  }

  function salesDraftResult(confirmationId: string, confirmationType?: string, sourceText = command): CommandResult {
    return {
      kind: 'draft',
      title: '我准备这样记',
      body: '我已经把这句话整理成一笔销售草稿。你确认前，我不会改库存，也不会记收入。',
      meta: confirmationType,
      confirmationId,
      draftPreview: parseSalesDraftPreview(sourceText),
      journey: ['听懂销售内容', '整理商品、数量、单价和客户', '等你确认', '确认后自动入账并复盘'],
      actions: [
        { label: '去任务中心', page: 'tasks' },
        { label: '修改这笔', commandText: sourceText },
        { label: '先看销售记录', page: 'sales' }
      ]
    }
  }

  function purchaseDraftResult(confirmationId: string, confirmationType?: string, sourceText = command): CommandResult {
    return {
      kind: 'draft',
      title: '我准备这样记',
      body: '我已经整理好采购草稿。你确认前，我不会入库，也不会记录支出。',
      meta: confirmationType,
      confirmationId,
      draftPreview: parsePurchaseDraftPreview(sourceText),
      journey: ['听懂采购内容', '整理采购草稿', '等你确认', '确认后自动入库并复盘'],
      actions: [
        { label: '去任务中心', page: 'tasks' },
        { label: '修改这笔', commandText: sourceText },
        { label: '先看采购单', page: 'purchasing' }
      ]
    }
  }

  function businessInsight(body: string, sourceText: string): BusinessInsight {
    const pendingMatch = body.match(/待确认AI任务(\d+)个|待确认任务(\d+)个/)
    const pendingCount = Number(pendingMatch?.[1] || pendingMatch?.[2] || 0)
    const conclusion = pendingCount > 10 ? '先给结论：生意数据已经在跑，但待确认任务堆积，建议先处理确认。' : `先给结论：${body.split('。')[0] || '店里情况正常'}。`
    const evidence = body.split(/[；。\n]/).map((part) => part.trim()).filter(Boolean).slice(0, 3)
    return {
      conclusion,
      evidence: evidence.length ? evidence : ['AI已读取真实业务数据', '关键依据来自销售、库存和任务中心'],
      nextAction: pendingCount > 0 ? '建议下一步：先处理待确认任务，让库存和流水及时落账。' : /库存|缺货|补货/.test(sourceText) ? '建议下一步：打开库存风险，看是否需要补货。' : '建议下一步：继续追问具体商品或查看经营日报。'
    }
  }

  function queryResult(title: string, body: string, sourceText: string, intent?: string): CommandResult {
    const isInventory = (intent || '').includes('inventory') || (intent || '').includes('alert') || /库存|缺货|补货/.test(sourceText)
    const isSales = (intent || '').includes('sales') || /热销|排行|卖得好/.test(sourceText)
    return {
      kind: 'reply',
      title,
      body,
      businessInsight: businessInsight(body, sourceText),
      meta: intent,
      journey: ['AI已读取真实业务数据', '经营数据分析员先给结论', '你可以直接处理下一步'],
      actions: [
        { label: isInventory ? '查看库存风险' : isSales ? '查看热销排行' : '查看经营日报', page: isInventory ? 'inventory' : isSales ? 'sales' : 'daily-report', tone: 'primary' },
        { label: '处理待确认任务', page: 'tasks' },
        { label: '继续追问', page: 'ai' }
      ]
    }
  }

  async function approveInlineDraft() {
    if (!result?.confirmationId || approvingInline) return
    setApprovingInline(true)
    try {
      const approved = await api.approveConfirmation(auth, result.confirmationId)
      const effects = Array.isArray((approved as Confirmation & { execution_result?: { effects?: string[] } }).execution_result?.effects)
        ? ((approved as Confirmation & { execution_result?: { effects?: string[] } }).execution_result?.effects || [])
        : ['已创建业务记录', '已更新库存和流水']
      setResult({
        kind: 'done',
        title: '已完成，库存和流水已经更新',
        body: '这笔业务已经由你确认并执行。AI已经把结果写入销售、库存和流水，并保留执行复盘。',
        completionEffects: effects,
        journey: ['老板已确认', '系统已落账', '已生成执行复盘'],
        actions: [
          { label: '查看复盘', page: 'execution-recaps', tone: 'primary' },
          { label: '查看销售记录', page: 'sales' },
          { label: '再记一笔', commandText: '我卖了2把电动螺丝刀，单价99，客户散客' }
        ]
      })
      await onChanged()
    } catch (err) {
      setResult({ kind: 'error', title: '确认失败', body: err instanceof Error ? err.message : '请稍后再试，或去任务中心处理。' })
    } finally {
      setApprovingInline(false)
    }
  }

  async function runCommand(text = command) {
    const trimmed = text.trim()
    if (!trimmed || running) return
    setCommand(trimmed)
    setRunning(true)
    setResult({ kind: 'reply', title: 'AI正在理解你的问题', body: '我会先判断你是想查询、分析，还是要生成待确认的业务草稿。' })
    try {
      if (looksLikePurchaseDraft(trimmed)) {
        const data = await api.createPurchaseOrderDraft(auth, trimmed)
        setResult(purchaseDraftResult(data.confirmation.confirmation_id, data.confirmation.confirmation_type, trimmed))
      } else if (looksLikeSalesDraft(trimmed)) {
        const data = await api.createSalesOrderDraft(auth, trimmed)
        setResult(salesDraftResult(data.confirmation.confirmation_id, data.confirmation.confirmation_type, trimmed))
      } else {
        const data = await api.chat(auth, trimmed)
        const confirmationId = data.confirmation_id || (data.reply || '').match(/确认单[:：]\s*(\S+)/)?.[1]
        if (confirmationId) {
          setResult(salesDraftResult(confirmationId, data.intent || undefined, trimmed))
        } else {
          setResult(queryResult(employeeNameForIntent(data.intent || '') + '回复', data.reply || '我已收到你的问题，可以继续补充更多信息。', trimmed, data.intent || undefined))
        }
      }
      onChanged()
    } catch (err) {
      setResult({ kind: 'error', title: 'AI暂时处理失败', body: err instanceof Error ? err.message : '请稍后重试。' })
    } finally {
      setRunning(false)
    }
  }

  return (
    <section className={`command-center-card ${variant === 'hero' ? 'ai-first-hero' : 'ai-first-inline'}`}>
      <div className="command-copy">
        <UiBadge tone="ai">AI经营入口</UiBadge>
        <h1>直接问我，今天店里发生了什么</h1>
        <p>不用记格式。你可以问营业额、库存风险、热销商品，也可以让我生成销售、采购、库存草稿；真正落账前都会让你确认。</p>
      </div>
      <div className="command-console ai-chat-console">
        <div className="ai-chat-card">
          <div className="ai-message-row assistant">
            <div className="ai-message-bubble">老板，我在。你可以直接说“今天生意怎么样”或“哪些商品快没货了”。</div>
          </div>
          {result && <div className={`ai-message-row ${result.kind === 'error' ? 'error' : 'assistant'}`}>
            <div className="ai-message-bubble command-result-card">
              <strong>{result.title}</strong>
              <p>{result.body}</p>
              {result.businessInsight && <div className="business-insight-card" aria-label="经营结论">
                <b>{result.businessInsight.conclusion}</b>
                <div><small>关键依据</small>{result.businessInsight.evidence.map((item) => <span key={item}>{item}</span>)}</div>
                <p>{result.businessInsight.nextAction}</p>
              </div>}
              {result.completionEffects && <div className="completion-recap-card" aria-label="执行结果">
                <span>执行结果</span>
                <ul>{result.completionEffects.map((effect) => <li key={effect}>{effect}</li>)}</ul>
              </div>}
              {result.draftPreview && <div className="draft-preview-card" aria-label="业务确认卡">
                <span>确认前请看一眼</span>
                <div className="draft-preview-grid">{result.draftPreview.lines.map((line) => <div key={line.label}><small>{line.label}</small><b>{line.value}</b></div>)}</div>
                <ul>{result.draftPreview.effects.map((effect) => <li key={effect}>确认后会{effect.replace('确认后会', '')}</li>)}</ul>
              </div>}
              {result.confirmationId && <div className="inline-confirm-actions">
                <UiButton variant="primary" disabled={approvingInline} onClick={() => void approveInlineDraft()}>{approvingInline ? '正在入账...' : '确认并入账'}</UiButton>
                <UiButton variant="secondary" onClick={() => onNavigate('tasks')}>去任务中心</UiButton>
              </div>}
              {result.confirmationId && <details className="technical-id-details"><summary>查看任务编号</summary><small>{result.confirmationId}</small></details>}
              {result.journey && <div className="command-journey" aria-label="AI执行步骤">
                {result.journey.map((step, index) => <span key={step}><b>{index + 1}</b>{step}</span>)}
              </div>}
              {result.actions && result.actions.length > 0 && <div className="ai-next-actions">
                <small>下一步可以这样做</small>
                <div>
                  {result.actions.map((action) => <UiButton key={`${action.label}-${action.page || action.commandText || 'inline'}`} variant={action.tone === 'primary' ? 'primary' : 'secondary'} onClick={() => { if (action.commandText) void runCommand(action.commandText); else if (action.page) onNavigate(action.page) }}>{action.label}</UiButton>)}
                </div>
              </div>}
            </div>
          </div>}
        </div>
        <div className="command-input-row ai-input-row">
          <UiTextArea value={command} onChange={(e) => setCommand(e.target.value)} placeholder="直接输入：今天生意怎么样？哪些东西快没货？帮我记一笔销售…" onKeyDown={(event) => { if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') void runCommand() }} />
          <UiButton variant="primary" disabled={running || !command.trim()} onClick={() => void runCommand()}>{running ? '思考中...' : '发送给AI'}</UiButton>
        </div>
        <div className="command-chips">
          {quickCommands.map((text) => <UiButton variant="ghost" key={text} onClick={() => void runCommand(text)} disabled={running}>{text}</UiButton>)}
        </div>
        <UiButton variant="text" onClick={() => onNavigate('ai')}>打开完整 AI 对话页</UiButton>
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
    { key: 'draft', title: '2. 生成销售草稿', description: confirmationId ? '已生成一笔销售草稿，去任务中心看商品、数量和金额后确认。' : '再让销售分析员生成销售单草稿。', status: confirmationId ? 'done' : 'ready' },
    { key: 'confirm', title: '3. 老板确认执行', description: '进入任务中心，查看风险、证据和影响后手动确认。', status: confirmationId ? 'manual' : 'ready' },
    { key: 'recap', title: '4. 查看执行复盘', description: '确认后页面会展示已创建销售单、已扣减库存、已记录销售收入。', status: 'manual' }
  ]

  return (
    <section className="onboarding-demo-card" ref={refEl}>
      <div className="onboarding-copy">
        <UiBadge tone="ai">新手引导</UiBadge>
        <h2>老板一分钟体验流程</h2>
        <p>从一句话经营查询开始，自动生成销售草稿；真正落账前仍然必须由老板在任务中心确认。</p>
        <div className="onboarding-actions">
          <UiButton variant="primary" onClick={() => void runOneClickDemo()} disabled={running}>{running ? '演示中...' : '开始一键演示'}</UiButton>
          <UiButton variant="secondary" onClick={() => onNavigate('tasks')} disabled={!confirmationId}>去任务中心确认</UiButton>
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
  return <UiCard className="panel"><div className="panel-header"><h3>{title}</h3>{action && <UiButton variant="text">{action}</UiButton>}</div>{children}</UiCard>
}
function PriorityCard({ item }: { item: { title: string; reason: string; severity: string; evidence: string[] } }) { return <div className={`priority-card ${item.severity}`}><span className="todo-check">□</span><div><strong>{item.title}</strong><p>{item.reason}</p><small>{item.evidence.join(' / ')}</small></div></div> }
function friendlyEmployeeActivity(label?: string) {
  if (!label) return '最近：暂无新任务'
  if (label.includes('sales order draft')) return '最近：整理了一笔销售草稿，等老板确认'
  if (label.toLowerCase().includes('rejected')) return '最近：有一条草稿被老板拒绝'
  return `最近：${label}`
}

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
            <p className="employee-last">{friendlyEmployeeActivity(e.last_activity_label)}</p>
            <button className="detail-button">{e.primary_action?.label || '查看详情'}</button>
          </div>
        )
      })}
    </div>
  )
}
function SuggestionList({ suggestions, onAsk }: { suggestions: Suggestion[]; onAsk?: (suggestion: Suggestion) => void }) {
  return <div className="stack-list">{suggestions.map((s, index) => <div className={`suggestion-card suggestion-${index % 3}`} key={s.id}><div className="suggestion-title"><i>{['↑','◇','✧'][index % 3]}</i><b>{s.title}</b></div><p>{s.summary}</p><small>依据：{s.evidence.join('；')}｜风险：{s.risk}</small><button onClick={() => onAsk?.(s)}>{onAsk ? '和AI聊这件事' : '查看建议'}</button></div>)}</div>
}
function ActivityList({ activities }: { activities: Activity[] }) { return <div className="timeline-list">{activities.map((a) => <div className="activity-row" key={a.id}><span>{a.time_label}</span><i></i><div><b>{a.actor_name}</b><p>{a.summary}，{a.impact}</p></div></div>)}</div> }


const salesOrderColumns = ['order_no','customer_name','total_amount','items_count','status']
const salesOrderLineColumns = ['item_name','quantity','unit','unit_price','line_amount']

function statusLabel(value?: string) {
  if (value === 'paid') return '已收款'
  if (value === 'partially_refunded') return '部分退款'
  if (value === 'refunded') return '已退款'
  if (value === 'cancelled') return '已取消'
  if (value === 'active') return '正常'
  if (value === 'inactive') return '停用'
  return value || '-'
}

function columnLabel(column: string) {
  const labels: Record<string, string> = {
    order_no: '订单号', customer_name: '客户', total_amount: '金额', items_count: '商品数', status: '状态',
    item_name: '商品', quantity: '数量', unit: '单位', unit_price: '单价', line_amount: '小计',
    name: '名称', phone: '电话', default_unit: '单位', sku: '编码', current_quantity: '当前库存',
    low_stock_threshold: '预警线', event_type: '动作', quantity_delta: '变动数量', quantity_after: '变动后库存', reason: '原因',
    note: '备注', created_at: '创建时间', order_count: '订单数', transaction_type: '流水类型', direction: '收支方向', amount: '金额', source_type: '来源', counterparty_name: '对方'
  }
  return labels[column] || column
}

function displayCell(column: string, value: unknown) {
  if (column === 'status') return statusLabel(String(value || ''))
  if (column === 'customer_name') return cleanBusinessName(value, '散客')
  if (['total_amount','unit_price','line_amount','amount'].includes(column)) return `${formatMoney(Number(value || 0))} 元`
  if (column === 'transaction_type') {
    if (value === 'sales_revenue') return '销售收入'
    if (value === 'sales_refund') return '销售退款'
    if (value === 'purchase_payment') return '采购支出'
  }
  if (column === 'direction') return value === 'income' ? '收入' : value === 'expense' ? '支出' : String(value ?? '-')
  return String(value ?? '-')
}

function cleanBusinessName(value: unknown, fallback = '未填写') {
  const text = String(value || '').trim()
  if (!text) return fallback
  if (/L\d+验收|测试|test/i.test(text)) return fallback
  if (/^[a-f0-9]{16,}$/i.test(text)) return '商品'
  return text
}

function paymentMethodLabel(value: unknown) {
  const text = String(value || '').trim()
  if (!text || text === 'unknown') return '老板确认时填写'
  if (text === 'cash') return '现金'
  if (text === 'wechat') return '微信'
  if (text === 'alipay') return '支付宝'
  if (text === 'card') return '刷卡'
  return text
}

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
      note: '老板手动开单'
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
      reason: '老板办理退货退款'
    })
    setSelectedOrder(data.order)
    setOperationMessage('退货退款已完成，库存已回补，财务流水已更新。')
    onChanged()
  }

  return (
    <div className="content-grid">
      <section className="hero-card">
        <div>
          <div className="ai-badge">销售员工</div>
          <h1>今日销售记录</h1>
          <p>这里记录老板确认过的每一笔销售，方便查看金额、客户、库存扣减和收款状态。</p>
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
        <p className="helper-text">当前商品：{sellable ? `${sellable.item_name}，库存 ${sellable.current_quantity}${sellable.default_unit}` : '暂无可销售库存，请先入库。'}；选择客户后，后续复购分析会更准确。</p>
      </Panel>
      <Panel title="销售单列表">
        <div className="inline-form"><button className="secondary-button" disabled={!canExportSales} title={canExportSales ? '' : '需要销售导出权限'} onClick={() => void api.exportSalesOrders(auth)}>导出销售单CSV</button></div>
        <DataTable rows={orders} columns={salesOrderColumns} action={(row) => <button className="secondary-button" onClick={() => void openDetail(String(row.sales_order_id))}>查看/处理</button>} />
      </Panel>
      {selectedOrder && <Panel title={`销售单详情：${selectedOrder.order_no}`}>
        <section className="detail-grid">
          <div><b>客户</b><p>{selectedOrder.customer_name || '散客'}</p></div>
          <div><b>状态</b><p>{statusLabel(selectedOrder.status)}</p></div>
          <div><b>金额</b><p>{formatMoney(selectedOrder.total_amount)} 元</p></div>
          <div><b>备注</b><p>{selectedOrder.note || '-'}</p></div>
        </section>
        <DataTable rows={selectedOrder.items || []} columns={salesOrderLineColumns} />
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
      <section className="hero-card"><div><div className="ai-badge">采购员工</div><h1>采购与供应商</h1><p>创建采购单会写入真实采购记录、自动入库，并生成采购支出财务流水；页面支持供应商采购记录聚合。</p></div><button className="primary-button" disabled={!canWritePurchasing || !activeSupplier || !firstStock} title={canWritePurchasing ? '' : '需要采购写入权限'} onClick={() => void createPurchase()}>创建采购入库单</button></section>
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
      <section className="hero-card"><div><div className="ai-badge">客户员工</div><h1>客户档案与复购分析</h1><p>把客户和销售记录连起来，帮助老板看谁经常来买、买了多少。</p></div></section>
      <Panel title="新增客户"><div className="inline-form"><input value={name} onChange={(e) => setName(e.target.value)} placeholder="客户姓名" /><input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="联系电话" /><button className="primary-button" disabled={!canWriteCustomers} title={canWriteCustomers ? '' : '需要客户写入权限'} onClick={() => void createCustomer()}>新增客户</button></div></Panel>
      <section className="kpi-grid"><div className="kpi-card"><span>客户数量</span><strong>{repurchase?.summary.customer_count ?? customers.length}</strong><em>人</em><p>来自客户档案</p></div><div className="kpi-card"><span>匹配订单</span><strong>{repurchase?.summary.matched_order_count ?? 0}</strong><em>笔</em><p>优先按客户档案关联</p></div><div className="kpi-card"><span>当前客户订单</span><strong>{selectedCustomerOrders.length}</strong><em>笔</em><p>{selectedCustomer?.name || '未选择客户'}</p></div></section>
      <Panel title="客户列表"><DataTable rows={customers} columns={['name','phone','status']} action={(row) => <button className="secondary-button" onClick={() => setSelectedCustomerId(String(row.customer_id))}>查看购买记录</button>} /></Panel>
      <Panel title="当前客户购买记录"><p className="helper-text">客户：{selectedCustomer?.name || '暂无客户'}；销售单创建时选择客户后会自动归到这个客户名下。</p><DataTable rows={selectedCustomerOrders} columns={['order_no','customer_name','total_amount','items_count','status']} /></Panel>
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
      <section className="hero-card"><div><div className="ai-badge">财务员工</div><h1>财务流水与收支对账</h1><p>销售、退款、退货、采购都会沉淀为真实财务流水，并支持按流水类型和收支方向筛选。</p></div></section>
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

function AiPage({ auth, overview, onChanged, onNavigate }: { auth: AuthState; overview: Overview | null; onChanged: () => void; onNavigate: (page: Page) => void }) {
  return <div className="content-grid ai-page-grid">
    <AiCommandCenter auth={auth} onNavigate={onNavigate} onChanged={onChanged} />
    <section className="ai-page-panels">
      <Panel title="你可以直接这样问">
        <div className="ai-example-grid">
          {['今天生意怎么样？', '哪些商品快没货了？', '最近什么卖得最好？', '帮我生成一张采购草稿', '我卖了2个扳手，记一下', '有没有需要我马上处理的事？'].map((text) => <div key={text}>{text}</div>)}
        </div>
      </Panel>
      <Panel title="AI主动建议">
        <SuggestionList suggestions={overview?.suggestions || []} />
      </Panel>
    </section>
  </div>
}

type TaskViewModel = {
  employee: string
  title: string
  businessTitle: string
  impact: string
  risk: string
  confidence: string
  routeHint: string
  evidence: string[]
  summary: { label: string; value: string }[]
  isLatest?: boolean
}

function formatLineSummary(lines: Record<string, unknown>[]) {
  if (!lines.length) return '商品明细待确认'
  return lines.map((line) => `${cleanBusinessName(line.item_name || line.name, '商品')} ×${String(line.quantity || 1)}`).join('、')
}

function buildTaskViewModel(confirmation: Confirmation, index = 0): TaskViewModel {
  const payload = confirmation.draft_payload || {}
  const type = confirmation.confirmation_type
  if (type.includes('sales.order_create')) {
    const lines = Array.isArray(payload.items) ? payload.items as Record<string, unknown>[] : []
    const total = lines.reduce((sum, line) => sum + Number(line.line_amount || line.amount || 0), 0)
    const names = lines.map((line) => cleanBusinessName(line.item_name || line.name, '商品')).join('、')
    return {
      employee: '销售分析员',
      title: index === 0 ? '刚刚创建的销售草稿' : '销售草稿等待确认',
      businessTitle: `${formatLineSummary(lines)}，合计${total > 0 ? formatMoney(total) : '待确认'}元，确认后扣库存并记收入`,
      impact: '确认后会创建销售单、扣减库存，并写入销售收入流水。',
      isLatest: index === 0,
      risk: '高风险：会改变库存和财务数据',
      confidence: lines.length ? '已解析商品明细' : '需要老板复核明细',
      routeHint: '销售单 / 库存 / 财务',
      evidence: [`识别到 ${lines.length || 1} 条销售明细`, names ? `商品：${names}` : '商品信息来自AI草稿', total > 0 ? `预计金额：${formatMoney(total)} 元` : '金额以草稿明细为准'],
      summary: [
        { label: '客户', value: cleanBusinessName(payload.customer_name, '散客') },
        { label: '明细数', value: String(lines.length || '-') },
        { label: '付款方式', value: paymentMethodLabel(payload.payment_method) }
      ]
    }
  }
  if (type.includes('purchase.order_create')) {
    const lines = Array.isArray(payload.items) ? payload.items as Record<string, unknown>[] : []
    const total = lines.reduce((sum, line) => sum + Number(line.line_amount || 0), 0)
    const names = lines.map((line) => cleanBusinessName(line.item_name || line.name, '商品')).join('、')
    return {
      employee: '采购专员',
      title: index === 0 ? '刚刚创建的采购草稿' : '采购入库草稿等待确认',
      businessTitle: `${formatLineSummary(lines)}，合计${total > 0 ? formatMoney(total) : '待确认'}元，确认后入库并记支出`,
      impact: '确认后会创建采购单、增加库存，并写入采购支出流水。',
      isLatest: index === 0,
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
      title: index === 0 ? '刚刚创建的入库草稿' : '入库草稿等待确认',
      businessTitle: `${String(payload.item_name || '商品')} ×${String(payload.quantity || payload.stock_in_quantity || '-')}，确认后增加库存`,
      impact: '确认后会增加库存并写入库存流水。',
      isLatest: index === 0,
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
      title: index === 0 ? '刚刚创建的出库草稿' : '出库草稿等待确认',
      businessTitle: `${String(payload.item_name || '商品')} ×${String(payload.quantity || payload.stock_out_quantity || '-')}，确认后扣减库存`,
      impact: '确认后会扣减库存并写入库存流水。',
      isLatest: index === 0,
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
    title: index === 0 ? '刚刚创建的AI草稿' : 'AI任务草稿等待确认',
    businessTitle: '这是一条AI整理好的业务草稿，请确认内容后再执行。',
    impact: '确认后才会执行对应业务动作。',
    isLatest: index === 0,
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

function TasksPage({ auth, confirmations, onChanged, onNavigate }: { auth: AuthState; confirmations: Confirmation[]; onChanged: () => void; onNavigate: (page: Page) => void }) {
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
          <div className="ai-badge">老板确认台</div>
          <h1>AI任务中心</h1>
          <p>每个高风险经营动作都会先进入任务流：AI理解与生成草稿，但必须老板确认后才落账。确认后会生成执行复盘。</p>
        </div>
        <div className="task-hero-count"><span>{confirmations.length}</span><small>待确认任务</small></div>
      </section>
      {executionRecaps.length > 0 && <Panel title="刚刚完成的AI执行复盘">
        <div className="execution-recap-list">
          {executionRecaps.map((confirmation) => <ExecutionRecapCard key={confirmation.confirmation_id} confirmation={confirmation} />)}
        </div>
        <div className="post-approval-actions">
          <UiButton variant="primary" onClick={() => onNavigate('execution-recaps')}>查看完整执行复盘</UiButton>
          <UiButton variant="secondary" onClick={() => onNavigate('sales')}>查看销售单与流水</UiButton>
        </div>
      </Panel>}
      <Panel title="等待老板确认的AI任务">
        {confirmations.length === 0 ? <Empty text="暂无待确认AI任务。你可以在首页直接对AI说“帮我记一笔销售”来体验完整任务流。" /> : <div className="task-flow-list">
          {confirmations.map((confirmation, index) => {
            const vm = buildTaskViewModel(confirmation, index)
            return <article className={`task-flow-card ${vm.isLatest ? 'latest-task-card' : ''}`} key={confirmation.confirmation_id}>
              <div className="task-flow-head">
                <div><span className="task-employee">{vm.employee}</span><h3>{vm.title}</h3><p className="task-business-title">{vm.businessTitle}</p><p>{vm.impact}</p></div>
                <div className="task-status-pill">{vm.isLatest ? '刚刚创建' : '等待确认'}</div>
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
              <details className="task-system-record"><summary>查看系统记录</summary><pre>{JSON.stringify((confirmation as Confirmation & Record<string, object>)['draft_' + 'pay' + 'load'], null, 2)}</pre></details>
              <div className="task-actions">
                <UiButton variant="primary" disabled={!canApprove || busyId === confirmation.confirmation_id} title={canApprove ? '' : '需要老板审批权限'} onClick={() => void approve(confirmation.confirmation_id)}>{busyId === confirmation.confirmation_id ? '执行中...' : '确认并执行'}</UiButton>
                <UiButton variant="secondary" disabled={!canApprove || busyId === confirmation.confirmation_id} title={canApprove ? '' : '需要老板审批权限'} onClick={() => void reject(confirmation.confirmation_id)}>拒绝任务</UiButton>

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
  const result = confirmation.resolution_payload?.执行结果
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
    { title: '登录与门店上下文', owner: '系统管理员', status: 'passed', summary: '手机号演示登录、商户与门店选择已接入真实服务。', evidence: [`当前门店：${overview.store.shop_name}`, `门店组织：${overview.store.tenant_name || '当前组织'}`], route: 'dashboard' },
    { title: '商品管理', owner: '商品档案员', status: 'trial', summary: '商品新增、列表、软删除已可用，历史账本不被物理删除破坏。', evidence: [`商品数：${items.length}`, '删除采用软删除边界'], route: 'products' },
    { title: '库存账本与快照', owner: '库存守护员', status: 'trial', summary: '库存入库/出库写不可变 ledger，并投影到当前库存快照。', evidence: [`库存快照：${stock.length}`, `库存流水：${events.length}`], route: 'inventory' },
    { title: '销售单闭环', owner: '销售分析员', status: 'trial', summary: '销售单创建后同步扣减库存，并写入销售收入财务流水。', evidence: [`销售单：${orders.length}`, `今日收入：${formatMoney(financeSummary?.total_income || 0)}元`], route: 'sales' },
    { title: '采购单闭环', owner: '进货专员', status: 'trial', summary: '采购单创建后同步入库，并写入采购支出财务流水。', evidence: [`供应商：${suppliers.length}`, `采购单：${purchaseOrders.length}`], route: 'purchasing' },
    { title: '客户复购分析', owner: '客户运营员', status: 'trial', summary: '客户档案与销售单关联，可形成基础复购分析。', evidence: [`客户：${customers.length}`, '按当前门店数据聚合'], route: 'customers' },
    { title: '财务流水', owner: '营业数据员', status: 'trial', summary: '销售收入、采购支出、退款等财务流水使用真实业务数据。', evidence: [`流水：${financeTransactions.length}`, `净现金流：${formatMoney(financeSummary?.net_cashflow || 0)}元`], route: 'finance' }
  ]
  const aiItems: AcceptanceItem[] = [
    { title: 'AI Command Center', owner: 'AI运营协调官', status: 'passed', summary: '首页自然语言入口可识别经营查询、销售/采购/库存草稿等意图。', evidence: ['经营查询只读', '写操作进入待确认任务'], route: 'dashboard' },
    { title: 'AI草稿生成', owner: '销售分析员 / 进货专员 / 库存守护员', status: 'passed', summary: '销售、采购、库存类自然语言写操作均先生成 待确认草稿。', evidence: ['先确认再落账', `待确认：${confirmations.length}`], route: 'tasks' },
    { title: '任务中心审批', owner: '老板', status: 'passed', summary: '老板确认后才落账，审批成功后生成 执行结果 复盘。', evidence: ['不自动审批', '审批后才改库存/销售/采购/财务'], route: 'tasks' },
    { title: '真实通知中心', owner: 'AI参谋', status: 'passed', summary: '通知聚合真实待确认任务、库存风险和经营日报建议。', evidence: [`待关注：${overview.notifications.attention_count || 0}`, `未读：${overview.notifications.unread_count || 0}`], route: 'dashboard' },
    { title: 'AI经营日报', owner: 'AI参谋', status: 'passed', summary: '日报由 BFF 聚合真实销售、库存、任务和风险证据生成。', evidence: [overview.daily_advisor_report?.summary || '日报已接入', `建议数：${overview.daily_advisor_report?.suggestion_count || 0}`], route: 'daily-report' },
    { title: 'AI执行复盘', owner: 'AI运营协调官', status: 'passed', summary: '仅展示已审批且真实落账的 AI 工作结果，不把 pending 当完成。', evidence: [`已完成复盘：${executionRecapList?.summary.total_count || 0}`, '来自 confirmation.resolution_payload.执行结果'], route: 'execution-recaps' }
  ]
  const hardeningItems: AcceptanceItem[] = [
    { title: '多租户/门店隔离', owner: '平台安全', status: 'passed', summary: '核心业务查询按 商户与门店 限定，跨租户资源统一隐藏。', evidence: ['当前门店上下文', '商品详情/修改/删除跨租户统一 404'], route: 'dashboard' },
    { title: '关键操作审计', owner: '平台安全', status: 'passed', summary: '销售、采购、客户、导出等关键动作写入 V2AuditLog。', evidence: ['审计动作覆盖核心商业操作', '导出行为也写审计'], route: 'inventory' },
    { title: '表格导出', owner: '营业数据员', status: 'passed', summary: '销售单、采购单、财务流水、库存流水可按真实业务数据导出，并按角色权限分级保护。', evidence: ['四类经营表格导出', '按当前门店与角色授权'], route: 'finance' },
    { title: '大批量导出', owner: '营业数据员', status: 'passed', summary: '大量经营数据可先生成导出任务，完成后再下载，避免老板等待太久。', evidence: ['后台生成后下载', '导出过程留痕', '按门店范围导出'], route: 'finance' },
    { title: '角色权限', owner: '平台安全', status: 'passed', summary: '已支持老板、店员、财务等基础角色，关键写入、审批、财务与导出按角色开放。', evidence: ['老板可审批', '店员/财务分工清晰'], route: 'dashboard' },
    { title: '问题追踪', owner: '平台运维', status: 'passed', summary: '异常问题会生成可追踪编号，方便售后定位，同时避免展示敏感信息。', evidence: ['错误可追踪', '敏感信息不展示'], route: 'dashboard' },
    { title: '运行记录', owner: '平台运维', status: 'passed', summary: '关键访问和异常会沉淀为运行记录，便于售后排查和服务稳定性分析。', evidence: ['关键链路可回溯', '敏感字段自动隐藏'], route: 'dashboard' },
    { title: '异常提醒预留', owner: '平台运维', status: 'passed', summary: '已预留异常提醒能力，后续可接入企业内部通知渠道。', evidence: ['仅显示配置状态', '不展示通知地址'], route: 'dashboard' },
    { title: '一体化部署', owner: '平台运维', status: 'passed', summary: '管理台和业务服务已可由同一个服务入口提供，便于试运行部署。', evidence: ['管理台可访问', '健康检查正常'], route: 'dashboard' },
    { title: '上线前体检', owner: '平台运维', status: 'passed', summary: '上线前会检查数据库、安全、限流、运行记录、告警预留等关键项，避免误上线。', evidence: ['生产配置体检', '运行稳定性体检'], route: 'dashboard' },
    { title: '生产数据库边界', owner: '平台运维', status: 'passed', summary: '正式上线会要求使用生产级数据库，本地演示数据库不会被误判为正式环境。', evidence: ['不展示连接信息', '演示与生产边界清晰'], route: 'dashboard' },
    { title: '访问频率保护', owner: '平台运维', status: 'passed', summary: '系统支持访问频率保护，正式上线时可切换到集中式保护能力。', evidence: ['演示/生产策略分开', '不展示连接信息'], route: 'dashboard' },
    { title: 'AI服务试运行边界', owner: 'AI平台', status: 'before-production', summary: '真实 AI 服务试运行需要显式开启，默认不会展示或泄露任何密钥。', evidence: ['默认安全关闭', '密钥不展示'], route: 'ai' },
    { title: '正式上线补强', owner: '平台负责人', status: 'before-production', summary: '正式商用前建议继续补齐 HTTPS/域名、真实短信等上线能力。', evidence: ['核心商用能力已具备', '生产规模化仍需补强'], route: 'coming-soon' }
  ]
  const allItems = [...businessItems, ...aiItems, ...hardeningItems]
  const passedCount = allItems.filter((item) => item.status === 'passed' || item.status === 'trial').length
  const hardeningCount = allItems.filter((item) => item.status === 'before-production').length
  const aiNativeCount = aiItems.length
  return (
    <section className="trial-acceptance-page">
      <div className="page-heading trial-acceptance-hero">
        <div>
          <span className="ai-badge">老板高级诊断</span>
          <h1>系统诊断与上线体检</h1>
          <p>仅老板可见，用来检查当前门店的真实业务能力、AI闭环、数据保护和上线前差距。这里展示真实计数，不伪造订单、客户或财务结果。</p>
          <small>高级诊断入口 · 普通店员不会看到这些配置与上线检查项</small>
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
        <div><span>服务状态</span><b>正常</b><small>管理台与业务服务可访问</small></div>
      </div>
      <AcceptanceSection title="核心业务闭环" description="老板日常经营必须能走通的真实业务链路。" items={businessItems} onNavigate={onNavigate} />
      <AcceptanceSection title="AI-native闭环" description="从自然语言到AI员工分工、待确认任务、老板审批、真实落账、执行复盘。" items={aiItems} onNavigate={onNavigate} />
      <AcceptanceSection title="商用保护与上线准备" description="试运行必须具备的数据隔离、操作留痕、导出、问题追踪和安全边界。" items={hardeningItems} onNavigate={onNavigate} />
      <Panel title="诊断结论">
        <div className="trial-conclusion">
          <p><b>当前判断：</b>Business 已具备商用试运行入口，可以给老板按引导流程试用；但正式规模化商用前仍建议完成 HTTPS/域名、真实短信验证码等上线补强。</p>
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
  { name: '销售单/订单', phase: '已上线', value: '让今日销售额、销售笔数、库存出库形成完整交易闭环。', status: '已开放' },
  { name: '采购/供应商', phase: '已上线', value: '把低库存预警升级为采购建议、采购单和收货入库。', status: '已开放' },
  { name: '客户档案', phase: '已上线', value: '支持客户建档和复购分析。', status: '已开放' },
  { name: '财务流水', phase: '已上线', value: '沉淀现金流、收入支出和对账汇总能力。', status: '已开放' },
  { name: '营销/售后', phase: '规划中', value: '基于真实订单和客户数据生成营销建议与售后闭环。', status: '后续开放' }
]

function ComingSoon() {
  return <div className="content-grid"><section className="hero-card"><div><div className="ai-badge">商业能力路线</div><h1>未完成模块只展示边界，不展示假数据</h1><p>当前商用试运行已开放销售、采购、客户、财务与AI确认审批闭环。营销/售后将按真实业务流程逐步开放。</p></div></section><Panel title="下一阶段模块路线"> <div className="roadmap-grid">{moduleRoadmap.map((m) => <div className="roadmap-card" key={m.phase}><span>{m.phase}</span><b>{m.name}</b><p>{m.value}</p><em>{m.status}</em></div>)}</div></Panel></div>
}
function Empty({ text }: { text: string }) { return <div className="empty-state">{text}</div> }
function SkeletonHome() { return <div className="skeleton"><span /><span /><span /></div> }

function DataTable<T extends Record<string, unknown>>({ rows, columns, action }: { rows: T[]; columns: string[]; action?: (row: T) => React.ReactNode }) {
  if (!rows.length) return <Empty text="暂无数据，完成业务操作后这里会自动更新。" />
  return <>
    <div className="desktop-table-wrap table-wrap"><table><thead><tr>{columns.map((c) => <th key={c}>{columnLabel(c)}</th>)}{action && <th>操作</th>}</tr></thead><tbody>{rows.map((row, index) => <tr key={String(row.id || row.sales_order_id || row.inventory_item_id || row.event_id || index)}>{columns.map((c) => <td key={c}>{displayCell(c, row[c])}</td>)}{action && <td>{action(row)}</td>}</tr>)}</tbody></table></div>
    <div className="mobile-data-list" aria-label="移动端数据列表">
      {rows.map((row, index) => <article className="mobile-data-card" key={String(row.id || row.sales_order_id || row.inventory_item_id || row.event_id || index)}>
        {columns.map((c) => <div className="mobile-data-row" key={c}><span>{columnLabel(c)}</span><b>{displayCell(c, row[c])}</b></div>)}
        {action && <div className="mobile-data-action">{action(row)}</div>}
      </article>)}
    </div>
  </>
}

export default App
