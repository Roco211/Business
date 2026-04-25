
export type ApiEnvelope<T> = { data: T; error?: { code: string; message: string } }

export type Tenant = { tenant_id?: string; tenantId?: string; name: string; role_key?: string; roleKey?: string }
export type Shop = { shop_id?: string; shopId?: string; tenant_id?: string; tenantId?: string; code: string; name: string; access_level?: string; accessLevel?: string }
export type AuthState = {
  accessToken: string
  refreshToken?: string
  accountId?: string
  contextToken: string
  tenantId: string
  shopId: string
}

export type Kpi = { key: string; label: string; value: number | string; unit?: string; trend_label?: string; status?: string }
export type AiEmployee = {
  key: string
  name: string
  description: string
  status: string
  status_label?: string
  today_task_count?: number
  pending_confirmation_count?: number
  completed_task_count?: number
  failed_task_count?: number
  last_activity_label?: string
  metrics: { label: string; value: number | string; unit?: string }[]
  primary_action?: { label: string; route: string }
}
export type Priority = { id: string; title: string; reason: string; severity: string; evidence: string[]; action: { label: string; route: string } }
export type Suggestion = { id: string; type: string; title: string; summary: string; evidence: string[]; risk: string; confidence: string; requires_confirmation: boolean; action: { label: string; route: string } }
export type DailyAdvisorReport = {
  title: string
  generated_by: string
  summary: string
  business_health: string
  report_date?: string
  generated_at?: string
  sections: { key: string; title: string; content: string; metrics: Record<string, number | string>; employee: string }[]
  next_actions: { title: string; reason: string; route: string; label: string }[]
  risk_notes: string[]
  suggestion_count: number
  execution_recaps?: { id: string; summary: string; status: string; intent_type?: string; risk_level?: string; created_at?: string; route: string }[]
  timeline?: { time_label: string; actor_name: string; summary: string; route: string }[]
  history?: DailyReportHistoryItem[]
  evidence: Record<string, number | string>
}
export type DailyReportHistoryItem = {
  report_date: string
  title: string
  summary: string
  business_health: string
  total_revenue: number
  transaction_count: number
  low_stock_count: number
  pending_confirmation_count: number
  route: string
}
export type DailyReportHistory = { items: DailyReportHistoryItem[] }
export type ExecutionRecapItem = {
  confirmation_id: string
  task_run_id: string
  kind: string
  status: string
  summary: string
  effects: string[]
  next_route: string
  created_at: string
  resolved_at: string
  source_employee: string
  intent_type?: string
  risk_level?: string
  evidence: string[]
}
export type ExecutionRecapList = {
  summary: { total_count: number; sales_order_count: number; purchase_order_count: number; inventory_count: number; other_count: number }
  items: ExecutionRecapItem[]
  generated_at?: string
}
export type Activity = { id: string; time_label: string; actor_name: string; summary: string; impact: string; route: string }
export type TodoItem = { key: string; title: string; count: number; severity: string; route: string }
export type NotificationItem = {
  id: string
  type: string
  title: string
  summary: string
  severity: string
  source_employee: string
  route: string
  action_label: string
  evidence: string[]
  created_at: string
  read?: boolean
}
export type Notifications = { unread_count: number; attention_count?: number; generated_at?: string; items?: NotificationItem[] }
export type Overview = {
  store: { tenant_id: string; tenant_name?: string; shop_id: string; shop_name: string; plan_label: string }
  user: { account_id: string; display_name: string; role_label: string }
  kpis: Kpi[]
  ai_employees: AiEmployee[]
  top_priorities: Priority[]
  suggestions: Suggestion[]
  activities: Activity[]
  daily_advisor_report?: DailyAdvisorReport
  todos: TodoItem[]
  notifications: Notifications
  low_stock?: { count: number; items: StockItem[] }
  sales_ranking?: SalesRank[]
  daily_revenue_series?: unknown[]
  coming_soon_modules?: { key: string; label: string }[]
}

export type InventoryItem = { inventory_item_id: string; tenant_id: string; sku?: string | null; name: string; barcode?: string | null; default_unit: string; status: string; created_at?: string; updated_at?: string }
export type StockItem = { snapshot_id: string; tenant_id: string; shop_id: string; inventory_item_id: string; item_name: string; default_unit: string; current_quantity: number; current_price?: number | null; low_stock_threshold?: number | null; updated_at?: string }
export type LedgerEvent = { event_id: string; inventory_item_id: string; item_name: string; event_type: string; quantity_delta: number; quantity_after: number; unit: string; price?: number | null; reason?: string | null; occurred_at: string }
export type SalesOrderLine = { sales_order_line_id: string; sales_order_id: string; inventory_item_id: string; item_name: string; quantity: number; unit: string; unit_price: number; line_amount: number }
export type SalesOrder = { sales_order_id: string; tenant_id: string; shop_id: string; order_no: string; status: string; customer_id?: string | null; customer_name?: string | null; payment_method: string; total_amount: number; items_count: number; items?: SalesOrderLine[]; note?: string | null; created_at: string; updated_at?: string }
export type Supplier = { supplier_id: string; tenant_id: string; shop_id: string; name: string; phone?: string | null; status: string; created_at?: string }
export type PurchaseOrder = { purchase_order_id: string; tenant_id: string; shop_id: string; supplier_id: string; order_no: string; status: string; total_amount: number; note?: string | null; created_at: string }
export type Customer = { customer_id: string; tenant_id: string; shop_id: string; name: string; phone?: string | null; status: string; created_at?: string }
export type CustomerRepurchaseAnalysis = { summary: { customer_count: number; matched_order_count: number }; customers: { customer_id: string; name: string; phone?: string | null; order_count: number; total_amount: number }[] }
export type FinanceTransaction = { finance_transaction_id: string; tenant_id: string; shop_id: string; transaction_type: string; direction: string; amount: number; source_type: string; source_id: string; counterparty_name?: string | null; note?: string | null; occurred_at: string }
export type FinanceSummary = { total_income: number; total_expense: number; net_cashflow: number }
export type SalesRank = { rank: number; item_id: string; item_name: string; sku?: string | null; total_sold: number; total_revenue: number; avg_price: number }
export type Confirmation = { confirmation_id: string; confirmation_type: string; status: string; draft_payload: Record<string, unknown>; resolution_payload?: Record<string, unknown> | null; created_at?: string }
