import client from './client';
import type { InventoryItem, StockInRequest, StockOutRequest } from '../types';

export const inventoryApi = {
  getItems(params?: { category?: string; low_stock?: boolean; search?: string }) {
    return client.get<{ data: InventoryItem[] }>('/items', { params });
  },

  getItem(itemId: string) {
    return client.get<{ data: InventoryItem }>(`/items/${itemId}`);
  },

  createItem(data: { name: string; category?: string; default_unit?: string; current_stock?: number; unit_price?: number; low_stock_threshold?: number }) {
    return client.post('/items', data);
  },

  stockIn(data: StockInRequest) {
    return client.post('/stock-in', data);
  },

  stockOut(data: StockOutRequest) {
    return client.post('/stock-out', data);
  },

  correctStock(data: { item_id: string; target_stock: number; reason: string }) {
    return client.post('/correction', data);
  },
};
