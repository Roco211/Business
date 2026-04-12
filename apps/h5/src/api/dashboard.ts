import client from './client';
import type { DashboardData, RevenueData, TransactionData, RecommendationsData, InventoryEvent } from '../types';

export const dashboardApi = {
  getDashboard() {
    return client.get<{ data: DashboardData }>('/dashboard');
  },

  getRevenue() {
    return client.get<{ data: RevenueData }>('/revenue');
  },

  getTransactions(limit = 20) {
    return client.get<{ data: TransactionData }>('/transactions', { params: { limit } });
  },

  getEvents(params?: { item_id?: string; limit?: number }) {
    return client.get<{ data: InventoryEvent[] }>('/events', { params });
  },

  getRecommendations() {
    return client.get<{ data: RecommendationsData }>('/recommendations');
  },
};
