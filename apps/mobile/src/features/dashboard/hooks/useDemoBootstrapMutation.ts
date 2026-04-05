import { useEffect, useRef, useState } from "react";

import { apiPostJson } from "../../../shared/api/client";


export type DemoBootstrapSummaryRecord = {
  shop_id: string;
  session_id: string;
  inventory_item_count: number;
  inventory_item_names: string[];
  pending_confirmation_count: number;
  pending_confirmation_types: string[];
  open_low_stock_alert_count: number;
  open_low_stock_item_names: string[];
  message_count: number;
  task_run_count: number;
};


type DemoBootstrapResponse = {
  data: DemoBootstrapSummaryRecord;
};


export function useDemoBootstrapMutation() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const isMountedRef = useRef(true);

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  async function runDemoBootstrap() {
    if (isMountedRef.current) {
      setIsSubmitting(true);
      setError(null);
      setSuccessMessage(null);
    }
    try {
      const response = await apiPostJson<DemoBootstrapResponse, Record<string, never>>(
        "/api/v1/system/demo/bootstrap",
        {},
      );
      if (isMountedRef.current) {
        setSuccessMessage("Demo state reset.");
      }
      return response.data;
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Failed to reset demo state";
      if (isMountedRef.current) {
        setError(message);
      }
      return null;
    } finally {
      if (isMountedRef.current) {
        setIsSubmitting(false);
      }
    }
  }

  return {
    isSubmitting,
    error,
    successMessage,
    runDemoBootstrap,
  };
}
