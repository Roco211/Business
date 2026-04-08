import { useEffect, useState } from "react";

import { apiGetJson } from "../../../shared/api/client";


export type DashboardSummaryRecord = {
  shop_id: string;
  today_stock_in_count: number;
  today_task_completed_count: number;
  pending_confirmations_count: number;
  open_low_stock_alert_count: number;
  last_inventory_event_at: string | null;
};


type DashboardSummaryResponse = {
  data: DashboardSummaryRecord;
};


export function useDashboardSummaryQuery() {
  const [data, setData] = useState<DashboardSummaryRecord | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshNonce, setRefreshNonce] = useState(0);

  useEffect(() => {
    let isActive = true;

    setIsLoading(true);
    setError(null);

    apiGetJson<DashboardSummaryResponse>("/api/v1/dashboard/summary")
      .then((response) => {
        if (!isActive) {
          return;
        }
        setData(response.data);
      })
      .catch((reason: unknown) => {
        if (!isActive) {
          return;
        }
        setError(reason instanceof Error ? reason.message : "Failed to load dashboard summary");
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [refreshNonce]);

  return {
    data,
    isLoading,
    error,
    refresh: () => setRefreshNonce((value) => value + 1),
  };
}
