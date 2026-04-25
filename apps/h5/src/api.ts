
import type { ApiEnvelope, AuthState, Confirmation, InventoryItem, LedgerEvent, Overview, Shop, StockItem, Tenant } from './types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
const AUTH_KEY = 'business_h5_auth'

export function loadAuth(): AuthState | null {
  const raw = localStorage.getItem(AUTH_KEY)
  if (!raw) return null
  try { return JSON.parse(raw) as AuthState } catch { return null }
}

export function saveAuth(auth: AuthState | null) {
  if (!auth) localStorage.removeItem(AUTH_KEY)
  else localStorage.setItem(AUTH_KEY, JSON.stringify(auth))
}

async function request<T>(path: string, options: RequestInit = {}, auth?: AuthState | null): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(options.headers as Record<string, string> | undefined) }
  if (auth?.accessToken) headers.Authorization = `Bearer ${auth.accessToken}`
  if (auth?.contextToken) headers['X-Context-Token'] = auth.contextToken
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const message = payload?.error?.message || payload?.detail || `请求失败(${response.status})`
    throw new Error(message)
  }
  return (payload as ApiEnvelope<T>).data
}

export async function loginWithPhone(phone: string, verificationCode: string): Promise<{ accessToken: string; refreshToken?: string; accountId?: string }> {
  const data = await request<{ accessToken?: string; access_token?: string; refreshToken?: string; refresh_token?: string; accountId?: string; account_id?: string }>('/api/v2/auth/login', {
    method: 'POST',
    body: JSON.stringify({ auth_method: 'phone_code', phone, verification_code: verificationCode })
  })
  return {
    accessToken: data.accessToken || data.access_token || '',
    refreshToken: data.refreshToken || data.refresh_token,
    accountId: data.accountId || data.account_id
  }
}

export async function bootstrapContext(accessToken: string, refreshToken?: string, accountId?: string): Promise<AuthState> {
  const partial: AuthState = { accessToken, refreshToken, accountId, contextToken: '', tenantId: '', shopId: '' }
  const tenantsData = await request<{ tenants: Tenant[] }>('/api/v2/me/tenants', {}, partial)
  const tenant = tenantsData.tenants[0]
  const tenantId = tenant?.tenant_id || tenant?.tenantId
  if (!tenantId) throw new Error('当前账号没有可用租户')
  const shopsData = await request<{ shops: Shop[] }>(`/api/v2/tenants/${tenantId}/shops`, {}, partial)
  const shop = shopsData.shops[0]
  const shopId = shop?.shop_id || shop?.shopId
  if (!shopId) throw new Error('当前租户没有可用门店')
  const context = await request<{ contextToken?: string; context_token?: string }>('/api/v2/context/select', {
    method: 'POST',
    body: JSON.stringify({ tenant_id: tenantId, shop_id: shopId })
  }, partial)
  const contextToken = context.contextToken || context.context_token || ''
  if (!contextToken) throw new Error('门店上下文创建失败')
  return { ...partial, contextToken, tenantId, shopId }
}

export const api = {
  getOverview: (auth: AuthState) => request<Overview>('/api/v2/pc-dashboard/overview', {}, auth),
  listItems: (auth: AuthState) => request<{ items: InventoryItem[]; count: number }>('/api/v2/inventory/items?limit=50', {}, auth),
  createItem: (auth: AuthState, input: { name: string; sku?: string; barcode?: string; default_unit: string }) => request<{ item: InventoryItem }>('/api/v2/inventory/items', { method: 'POST', body: JSON.stringify(input) }, auth),
  updateItem: (auth: AuthState, itemId: string, input: Partial<{ name: string; sku: string; barcode: string; default_unit: string }>) => request<{ item: InventoryItem }>(`/api/v2/inventory/items/${itemId}`, { method: 'PATCH', body: JSON.stringify(input) }, auth),
  deleteItem: (auth: AuthState, itemId: string) => request<{ item: InventoryItem }>(`/api/v2/inventory/items/${itemId}`, { method: 'DELETE' }, auth),
  listStock: (auth: AuthState) => request<{ items: StockItem[]; count: number }>('/api/v2/inventory/stock?limit=50', {}, auth),
  listEvents: (auth: AuthState) => request<{ events: LedgerEvent[]; count: number }>('/api/v2/inventory/events?limit=50', {}, auth),
  getAudit: (auth: AuthState, itemId: string) => request<{ events: LedgerEvent[]; count: number }>(`/api/v2/inventory/items/${itemId}/audit?limit=20`, {}, auth),
  stockIn: (auth: AuthState, input: { inventory_item_id: string; quantity: number; unit: string; price?: number; reason?: string }) => request<unknown>('/api/v2/inventory/stock-in', { method: 'POST', body: JSON.stringify(input) }, auth),
  stockOut: (auth: AuthState, input: { inventory_item_id: string; quantity: number; unit: string; price?: number; reason?: string }) => request<unknown>('/api/v2/inventory/stock-out', { method: 'POST', body: JSON.stringify(input) }, auth),
  chat: (auth: AuthState, message: string) => request<{ reply: string; intent?: string; confirmation_id?: string }>('/api/v2/chat', { method: 'POST', body: JSON.stringify({ message }) }, auth),
  listConfirmations: (auth: AuthState) => request<{ confirmations: Confirmation[]; count: number }>('/api/v2/confirmations?status=pending&limit=50', {}, auth),
  approveConfirmation: (auth: AuthState, confirmationId: string) => request<Confirmation>(`/api/v2/confirmations/${confirmationId}/approve`, { method: 'POST', body: JSON.stringify({ resolution_payload: {} }) }, auth),
  rejectConfirmation: (auth: AuthState, confirmationId: string) => request<Confirmation>(`/api/v2/confirmations/${confirmationId}/reject`, { method: 'POST' }, auth)
}
