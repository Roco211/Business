
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
export type AiEmployee = { key: string; name: string; description: string; status: string; metrics: { label: string; value: number | string; unit?: string }[]; primary_action?: { label: string; route: string } }
export type Priority = { id: string; title: string; reason: string; severity: string; evidence: string[]; action: { label: string; route: string } }
export type Suggestion = { id: string; type: string; title: string; summary: string; evidence: string[]; risk: string; confidence: string; requires_confirmation: boolean; action: { label: string; route: string } }
export type Activity = { id: string; time_label: string; actor_name: string; summary: string; impact: string; route: string }
export type TodoItem = { key: string; title: string; count: number; severity: string; route: string }
export type Overview = {
  store: { tenant_id: string; tenant_name?: string; shop_id: string; shop_name: string; plan_label: string }
  user: { account_id: string; display_name: string; role_label: string }
  kpis: Kpi[]
  ai_employees: AiEmployee[]
  top_priorities: Priority[]
  suggestions: Suggestion[]
  activities: Activity[]
  todos: TodoItem[]
  notifications: { unread_count: number }
  low_stock?: { count: number; items: StockItem[] }
  sales_ranking?: SalesRank[]
  daily_revenue_series?: unknown[]
  coming_soon_modules?: { key: string; label: string }[]
}

export type InventoryItem = { inventory_item_id: string; tenant_id: string; sku?: string | null; name: string; barcode?: string | null; default_unit: string; status: string; created_at?: string; updated_at?: string }
export type StockItem = { snapshot_id: string; tenant_id: string; shop_id: string; inventory_item_id: string; item_name: string; default_unit: string; current_quantity: number; current_price?: number | null; low_stock_threshold?: number | null; updated_at?: string }
export type LedgerEvent = { event_id: string; inventory_item_id: string; item_name: string; event_type: string; quantity_delta: number; quantity_after: number; unit: string; price?: number | null; reason?: string | null; occurred_at: string }
export type SalesRank = { rank: number; item_id: string; item_name: string; sku?: string | null; total_sold: number; total_revenue: number; avg_price: number }
export type Confirmation = { confirmation_id: string; confirmation_type: string; status: string; draft_payload: Record<string, unknown>; resolution_payload?: Record<string, unknown> | null; created_at?: string }
