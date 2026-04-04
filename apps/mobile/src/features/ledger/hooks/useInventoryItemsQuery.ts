import { useDeferredValue, useEffect, useState } from "react";

import { apiGetJson } from "../../../shared/api/client";


export type InventoryItemRecord = {
  item_id: string;
  name: string;
  default_unit: string;
  current_stock: string;
  current_price: string | null;
};


type InventoryItemsResponse = {
  data: InventoryItemRecord[];
  meta: {
    count: number;
  };
};


export function useInventoryItemsQuery(searchText: string) {
  const deferredSearchText = useDeferredValue(searchText.trim());
  const [data, setData] = useState<InventoryItemRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshNonce, setRefreshNonce] = useState(0);

  useEffect(() => {
    let isActive = true;

    setIsLoading(true);
    setError(null);

    const query = deferredSearchText ? `?query=${encodeURIComponent(deferredSearchText)}` : "";
    apiGetJson<InventoryItemsResponse>(`/api/v1/inventory-items${query}`)
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
        setError(reason instanceof Error ? reason.message : "Failed to load inventory");
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [deferredSearchText, refreshNonce]);

  return {
    data,
    isLoading,
    error,
    refresh: () => setRefreshNonce((value) => value + 1),
  };
}
