import { useEffect, useState } from "react";

import { apiGetJson } from "../../../shared/api/client";


export type AuditLogRecord = {
  audit_log_id: string;
  action: string;
  created_at: string;
  metadata: {
    item_name?: string;
    quantity_delta?: number;
    quantity_after?: number;
  };
};


type AuditLogsResponse = {
  data: AuditLogRecord[];
  meta: {
    count: number;
  };
};


export function useAuditLogsQuery() {
  const [data, setData] = useState<AuditLogRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    setIsLoading(true);
    setError(null);

    apiGetJson<AuditLogsResponse>("/api/v1/audit-logs?scope=inventory")
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
        setError(reason instanceof Error ? reason.message : "Failed to load audit logs");
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, []);

  return {
    data,
    isLoading,
    error,
  };
}
