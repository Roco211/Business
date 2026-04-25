
import { useEffect, useMemo, useState } from 'react'
import { api, bootstrapContext, loadAuth, loginWithPhone, saveAuth } from './api'
import type { Activity, AiEmployee, AuthState, Confirmation, Customer, CustomerRepurchaseAnalysis, FinanceSummary, FinanceTransaction, InventoryItem, LedgerEvent, Overview, PurchaseOrder, SalesOrder, StockItem, Suggestion, Supplier } from './types'
import './styles.css'

type Page = 'dashboard' | 'sales' | 'purchasing' | 'customers' | 'finance' | 'products' | 'inventory' | 'ai' | 'tasks' | 'coming-soon'

type LoadState = 'idle' | 'loading' | 'ready' | 'error'

const navItems: { page: Page; label: string }[] = [
  { page: 'dashboard', label: '工作台' },
  { page: 'sales', label: '销售单' },
  { page: 'purchasing', label: '采购单' },
  { page: 'customers', label: '客户复购' },
  { page: 'finance', label: '财务流水' },
  { page: 'products', label: '商品管理' },
  { page: 'inventory', label: '库存管理' },
  { page: 'ai', label: 'AI助手' },
  { page: 'tasks', label: '任务中心' },
  { page: 'coming-soon', label: '营销/售后' }
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
  const [orders, setOrders] = useState<SalesOrder[]>([])
  const [suppliers, setSuppliers] = useState<Supplier[]>([])
  const [purchaseOrders, setPurchaseOrders] = useState<PurchaseOrder[]>([])
  const [customers, setCustomers] = useState<Customer[]>([])
  const [repurchase, setRepurchase] = useState<CustomerRepurchaseAnalysis | null>(null)
  const [financeTransactions, setFinanceTransactions] = useState<FinanceTransaction[]>([])
  const [financeSummary, setFinanceSummary] = useState<FinanceSummary | null>(null)
  const [confirmations, setConfirmations] = useState<Confirmation[]>([])

  async function refresh(currentAuth = auth) {
    if (!currentAuth) return
    setState('loading')
    setError('')
    try {
      const [nextOverview, nextItems, nextStock, nextEvents, nextOrders, nextSuppliers, nextPurchaseOrders, nextCustomers, nextRepurchase, nextFinanceTransactions, nextFinanceSummary, nextConfirmations] = await Promise.all([
        api.getOverview(currentAuth),
        api.listItems(currentAuth),
        api.listStock(currentAuth),
        api.listEvents(currentAuth),
        api.listSalesOrders(currentAuth),
        api.listSuppliers(currentAuth),
        api.listPurchaseOrders(currentAuth),
        api.listCustomers(currentAuth),
        api.getCustomerRepurchaseAnalysis(currentAuth),
        api.listFinanceTransactions(currentAuth),
        api.getFinanceSummary(currentAuth),
        api.listConfirmations(currentAuth)
      ])
      setOverview(nextOverview)
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
        {page === 'sales' && <SalesPage auth={auth} stock={stock} orders={orders} customers={customers} onChanged={() => void refresh()} />}
        {page === 'purchasing' && <PurchasingPage auth={auth} stock={stock} suppliers={suppliers} purchaseOrders={purchaseOrders} onChanged={() => void refresh()} />}
        {page === 'customers' && <CustomersPage auth={auth} customers={customers} orders={orders} repurchase={repurchase} onChanged={() => void refresh()} />}
        {page === 'finance' && <FinancePage auth={auth} summary={financeSummary} transactions={financeTransactions} onTransactionsChanged={setFinanceTransactions} />}
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

function SalesPage({ auth, stock, orders, customers, onChanged }: { auth: AuthState; stock: StockItem[]; orders: SalesOrder[]; customers: Customer[]; onChanged: () => void }) {
  const sellable = stock.find((item) => Number(item.current_quantity || 0) > 0)
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
        <button className="primary-button" disabled={!sellable} onClick={() => void createOrder()}>创建销售单</button>
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
  const supplierOrders = activeSupplier ? purchaseOrders.filter((order) => order.supplier_id === activeSupplier.supplier_id) : []
  async function createSupplier() { if (!supplierName.trim()) return; await api.createSupplier(auth, { name: supplierName, phone: supplierPhone }); setSupplierName('默认五金供应商'); setSupplierPhone(''); onChanged() }
  async function createPurchase() { if (!activeSupplier || !firstStock) return; await api.createPurchaseOrder(auth, { supplier_id: activeSupplier.supplier_id, items: [{ inventory_item_id: firstStock.inventory_item_id, quantity: Number(quantity || 1), unit_cost: Number(unitCost || 0) }], note: 'PC/H5采购入库' }); onChanged() }
  return (
    <div className="content-grid">
      <section className="hero-card"><div><div className="ai-badge">H2 已增强</div><h1>采购/供应商闭环</h1><p>创建采购单会写入真实采购记录、自动入库，并生成采购支出财务流水；页面支持供应商采购记录聚合。</p></div><button className="primary-button" disabled={!activeSupplier || !firstStock} onClick={() => void createPurchase()}>创建采购入库单</button></section>
      <Panel title="新增供应商"><div className="inline-form"><input value={supplierName} onChange={(e) => setSupplierName(e.target.value)} placeholder="供应商名称" /><input value={supplierPhone} onChange={(e) => setSupplierPhone(e.target.value)} placeholder="联系电话" /><button className="primary-button" onClick={() => void createSupplier()}>新增供应商</button></div></Panel>
      <Panel title="快速采购入库"><div className="inline-form"><select value={activeSupplier?.supplier_id || ''} onChange={(e) => setSelectedSupplierId(e.target.value)}><option value="">选择供应商</option>{suppliers.map((supplier) => <option key={supplier.supplier_id} value={supplier.supplier_id}>{supplier.name}</option>)}</select><input value={quantity} onChange={(e) => setQuantity(e.target.value)} placeholder="采购数量" /><input value={unitCost} onChange={(e) => setUnitCost(e.target.value)} placeholder="采购单价" /></div><p className="helper-text">供应商：{activeSupplier?.name || '请先新增供应商'}；商品：{firstStock?.item_name || '暂无商品库存快照'}</p></Panel>
      <section className="kpi-grid"><div className="kpi-card"><span>供应商数量</span><strong>{suppliers.length}</strong><em>家</em><p>当前门店 active 供应商</p></div><div className="kpi-card"><span>采购单数量</span><strong>{purchaseOrders.length}</strong><em>单</em><p>当前门店采购记录</p></div><div className="kpi-card"><span>当前供应商采购</span><strong>{supplierOrders.length}</strong><em>单</em><p>{activeSupplier?.name || '未选择'}</p></div></section>
      <Panel title="供应商列表"><DataTable rows={suppliers} columns={['name','phone','status']} action={(row) => <button className="secondary-button" onClick={() => setSelectedSupplierId(String(row.supplier_id))}>查看采购记录</button>} /></Panel>
      <Panel title="当前供应商采购单"><DataTable rows={supplierOrders} columns={['order_no','status','total_amount','note','created_at']} /></Panel>
      <Panel title="全部采购单列表"><DataTable rows={purchaseOrders} columns={['order_no','status','total_amount','note','created_at']} /></Panel>
    </div>
  )
}

function CustomersPage({ auth, customers, orders, repurchase, onChanged }: { auth: AuthState; customers: Customer[]; orders: SalesOrder[]; repurchase: CustomerRepurchaseAnalysis | null; onChanged: () => void }) {
  const [name, setName] = useState('老王')
  const [phone, setPhone] = useState('')
  const [selectedCustomerId, setSelectedCustomerId] = useState('')
  const selectedCustomer = customers.find((customer) => customer.customer_id === selectedCustomerId) || customers[0]
  const selectedCustomerOrders = selectedCustomer ? orders.filter((order) => order.customer_id === selectedCustomer.customer_id || order.customer_name === selectedCustomer.name) : []
  async function createCustomer() { if (!name.trim()) return; await api.createCustomer(auth, { name, phone }); setName('老王'); setPhone(''); onChanged() }
  return (
    <div className="content-grid">
      <section className="hero-card"><div><div className="ai-badge">H2/H3 已增强</div><h1>客户档案与复购分析</h1><p>销售单已支持 customer_id 关联，复购分析优先按客户ID统计，避免同名客户误匹配。</p></div></section>
      <Panel title="新增客户"><div className="inline-form"><input value={name} onChange={(e) => setName(e.target.value)} placeholder="客户姓名" /><input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="联系电话" /><button className="primary-button" onClick={() => void createCustomer()}>新增客户</button></div></Panel>
      <section className="kpi-grid"><div className="kpi-card"><span>客户数量</span><strong>{repurchase?.summary.customer_count ?? customers.length}</strong><em>人</em><p>来自客户档案</p></div><div className="kpi-card"><span>匹配订单</span><strong>{repurchase?.summary.matched_order_count ?? 0}</strong><em>笔</em><p>优先按 customer_id 关联</p></div><div className="kpi-card"><span>当前客户订单</span><strong>{selectedCustomerOrders.length}</strong><em>笔</em><p>{selectedCustomer?.name || '未选择客户'}</p></div></section>
      <Panel title="客户列表"><DataTable rows={customers} columns={['name','phone','status']} action={(row) => <button className="secondary-button" onClick={() => setSelectedCustomerId(String(row.customer_id))}>查看购买记录</button>} /></Panel>
      <Panel title="当前客户购买记录"><p className="helper-text">客户：{selectedCustomer?.name || '暂无客户'}；销售单创建时选择客户后会自动关联 customer_id。</p><DataTable rows={selectedCustomerOrders} columns={['order_no','customer_name','total_amount','items_count','status']} /></Panel>
      <Panel title="复购分析"><DataTable rows={repurchase?.customers || []} columns={['name','phone','order_count','total_amount']} /></Panel>
    </div>
  )
}

function FinancePage({ auth, summary, transactions, onTransactionsChanged }: { auth: AuthState; summary: FinanceSummary | null; transactions: FinanceTransaction[]; onTransactionsChanged: (rows: FinanceTransaction[]) => void }) {
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
      <Panel title="流水筛选"><div className="inline-form"><select value={transactionType} onChange={(e) => setTransactionType(e.target.value)}><option value="">全部类型</option><option value="sales_revenue">销售收入</option><option value="sales_refund">销售退款</option><option value="purchase_payment">采购支出</option></select><select value={direction} onChange={(e) => setDirection(e.target.value)}><option value="">全部方向</option><option value="income">收入</option><option value="expense">支出</option></select><button className="secondary-button" onClick={() => void applyFilters()}>应用筛选</button></div></Panel>
      <Panel title="财务流水"><DataTable rows={transactions} columns={['transaction_type','direction','amount','source_type','counterparty_name','note']} /></Panel>
    </div>
  )
}

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
  const [draftMessage, setDraftMessage] = useState('卖出1把电动螺丝刀，单价99，客户老王')
  const [reply, setReply] = useState('')
  const [draftResult, setDraftResult] = useState('')
  async function send() { const data = await api.chat(auth, message); setReply(data.reply); onChanged() }
  async function createDraft() { const data = await api.createSalesOrderDraft(auth, draftMessage); setDraftResult(`已生成待确认销售单：${data.confirmation.confirmation_id}`); onChanged() }
  return <div className="content-grid"><section className="hero-card"><div><div className="ai-badge">AI运营协调官</div><h1>自然语言经营入口</h1><p>可查询营业数据、库存、热销排行；涉及业务写入时后端会生成待确认任务，审批后才落账。</p></div></section><Panel title="问AI运营协调官"><div className="chat-box"><textarea value={message} onChange={(e) => setMessage(e.target.value)} /><button className="primary-button" onClick={() => void send()}>发送</button>{reply && <div className="assistant-reply">{reply}</div>}</div></Panel><Panel title="AI生成销售单草稿"><div className="chat-box"><textarea value={draftMessage} onChange={(e) => setDraftMessage(e.target.value)} /><button className="primary-button" onClick={() => void createDraft()}>生成待确认销售单</button>{draftResult && <div className="assistant-reply">{draftResult}，请到任务中心审批。</div>}</div></Panel><Panel title="建议快捷入口"><SuggestionList suggestions={overview?.suggestions || []} /></Panel></div>
}

function TasksPage({ auth, confirmations, onChanged }: { auth: AuthState; confirmations: Confirmation[]; onChanged: () => void }) {
  async function approve(id: string) { await api.approveConfirmation(auth, id); onChanged() }
  async function reject(id: string) { await api.rejectConfirmation(auth, id); onChanged() }
  return <Panel title="AI待确认任务">{confirmations.length === 0 ? <Empty text="暂无待确认AI任务。" /> : <div className="stack-list">{confirmations.map((c) => <div className="task-card" key={c.confirmation_id}><b>{c.confirmation_type}</b><pre>{JSON.stringify(c.draft_payload, null, 2)}</pre><button className="primary-button" onClick={() => void approve(c.confirmation_id)}>批准落账</button><button className="secondary-button" onClick={() => void reject(c.confirmation_id)}>拒绝</button></div>)}</div>}</Panel>
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
