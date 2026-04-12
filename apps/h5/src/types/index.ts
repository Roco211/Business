// ============================================================
// AI五金店大管家 - 类型定义
// ============================================================

// -- 认证相关 --
export interface User {
  user_id: string;
  username: string;
  nickname?: string;
  shop_id: string;
}

export interface LoginResponse {
  success: boolean;
  message: string;
  user_id?: string;
  username?: string;
  nickname?: string;
  token?: string;
  user?: User;
}

export interface AuthState {
  token: string | null;
  user: User | null;
}

// -- 库存商品 --
export interface InventoryItem {
  item_id: string;
  name: string;
  category: string;
  default_unit: string;
  current_stock: number;
  unit_price: number;
  low_stock_threshold: number;
  is_low_stock: boolean;
  created_at: string;
  updated_at: string;
}

// -- 库存事件 --
export interface InventoryEvent {
  event_id: string;
  item_id: string;
  item_name: string;
  event_type: 'stock_in' | 'stock_out' | 'correction';
  quantity: number;
  unit: string;
  unit_price: number;
  reason: string;
  source: string;
  created_at: string;
}

// -- Dashboard --
export interface DashboardData {
  total_items: number;
  low_stock_items: number;
  total_value: number;
  today_events: number;
  categories: string[];
}

// -- 营收 --
export interface RevenueData {
  today_revenue: number;
  week_revenue: number;
  month_revenue: number;
  daily_revenue: Array<{ date: string; revenue: number }>;
  top_items: TopItem[];
}

export interface TopItem {
  name: string;
  total_sold: number;
  total_revenue: number;
  item_id?: string;
}

// -- 流水 --
export interface TransactionData {
  transactions: InventoryEvent[];
  today_stats: TodayStats;
}

export interface TodayStats {
  total_events: number;
  stock_in_count?: number;
  stock_out_count?: number;
  total_in: number;
  total_out: number;
  total_in_value: number;
  total_out_value: number;
}

// -- AI推荐 --
export interface Recommendation {
  type: 'urgent' | 'warning' | 'info' | 'success';
  title: string;
  items?: Array<{ name: string; stock?: number; threshold?: number; last_sold?: string }>;
  message?: string;
  action?: string;
  name?: string;
  item_name?: string;
  suggestion?: string;
  reason?: string;
  item_id?: string;
}

export interface RecommendationsData {
  recommendations: Recommendation[];
}

// -- AI聊天 --
export interface ChatRequest {
  message: string;
  session_id?: string;
}

export interface ChatResponse {
  reply: string;
  intent: string;
  action: string;
  data?: Record<string, unknown>;
}

// -- AI员工角色 --
export interface AIRole {
  name: string;
  color: string;
  key: string;
}

// -- 出入库请求 --
export interface StockInRequest {
  item_id: string;
  quantity: number;
  unit_price?: number;
  reason?: string;
}

export interface StockOutRequest {
  item_id: string;
  quantity: number;
  reason?: string;
}

// -- API通用响应 --
export interface ApiResponse<T> {
  data: T;
}
