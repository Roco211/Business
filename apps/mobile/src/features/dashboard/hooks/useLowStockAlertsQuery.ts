import { useEffect, useState } from "react";

import { apiGetJson } from "../../../shared/api/client";


export type LowStockAlertRecord = {
  alert_id: string;
  item_id: string;
  item_name: string;
  status: string;
  stock: string;
  threshold: string;
  unit: string;
};


type LowStockAlertsResponse = {
  data: LowStockAlertRecord[];
  meta: {
    count: number;
  };
};


export function useLowStockAlertsQuery() {
  const [data, setData] = useState<LowStockAlertRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshNonce, setRefreshNonce] = useState(0);

  useEffect(() => {
    let isActive = true;

    setIsLoading(true);
    setError(null);

    apiGetJson<LowStockAlertsResponse>("/api/v1/alerts?type=low-stock")
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
        setError(reason instanceof Error ? reason.message : "Failed to load low-stock alerts");
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
