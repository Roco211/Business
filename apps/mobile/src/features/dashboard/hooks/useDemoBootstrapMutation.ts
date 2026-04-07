import { useEffect, useRef, useState } from "react";

import { apiPostJson } from "../../../shared/api/client";
import { getFriendlyStatusMessage } from "../../../shared/copy/getFriendlyStatusMessage";


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
        setSuccessMessage("演示数据已刷新，可继续体验。");
      }
      return response.data;
    } catch (reason: unknown) {
      if (isMountedRef.current) {
        setError(
          getFriendlyStatusMessage(
            reason instanceof Error ? reason.message : null,
            "演示数据暂时无法重置，请稍后再试。",
          ),
        );
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
