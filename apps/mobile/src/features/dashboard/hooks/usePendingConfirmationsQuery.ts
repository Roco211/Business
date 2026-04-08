import { useEffect, useState } from "react";

import { apiGetJson } from "../../../shared/api/client";


export type PendingConfirmationRecord = {
  confirmation_id: string;
  confirmation_type: string;
  status: string;
  fields: {
    summary?: string;
  };
};


type PendingConfirmationsResponse = {
  data: PendingConfirmationRecord[];
  meta: {
    count: number;
  };
};


export function usePendingConfirmationsQuery() {
  const [data, setData] = useState<PendingConfirmationRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshNonce, setRefreshNonce] = useState(0);

  useEffect(() => {
    let isActive = true;

    setIsLoading(true);
    setError(null);

    apiGetJson<PendingConfirmationsResponse>("/api/v1/confirmations?status=pending&limit=20")
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
        setError(reason instanceof Error ? reason.message : "Failed to load confirmations");
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
