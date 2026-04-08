import { useEffect, useState } from "react";

import { apiGetJson } from "../../../shared/api/client";


type ConfirmationDraftFields = {
  item_name?: string | null;
  quantity?: number | null;
  unit?: string | null;
  price?: number | null;
};


export type ReceiptDraftItem = {
  line_id?: string;
  item_id?: string | null;
  item_name?: string | null;
  quantity?: number | null;
  unit?: string | null;
  price?: number | null;
};


type ConfirmationFields = {
  summary?: string;
  transcript?: string;
  draft_fields?: ConfirmationDraftFields;
  required_fields?: string[];
  ocr_document_id?: string;
  total_amount?: number;
  low_confidence_fields?: string[];
  draft_items?: ReceiptDraftItem[];
  required_item_fields?: string[];
};


export type ChatPendingConfirmationRecord = {
  confirmation_id: string;
  session_id: string;
  task_run_id: string;
  confirmation_type: string;
  status: string;
  fields: ConfirmationFields;
};


type PendingConfirmationsResponse = {
  data: Array<
    ChatPendingConfirmationRecord & {
      requested_by_employee_id: string | null;
      resolution_payload: Record<string, unknown> | null;
      approved_by_actor_id: string | null;
      created_at: string;
      resolved_at: string | null;
    }
  >;
  meta: {
    count: number;
  };
};


export function useChatPendingConfirmationsQuery(sessionId: string | null) {
  const [data, setData] = useState<ChatPendingConfirmationRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshNonce, setRefreshNonce] = useState(0);

  useEffect(() => {
    let isActive = true;

    if (sessionId === null) {
      setData([]);
      setError(null);
      setIsLoading(false);
      return () => {
        isActive = false;
      };
    }

    setIsLoading(true);
    setError(null);

    apiGetJson<PendingConfirmationsResponse>("/api/v1/confirmations?status=pending&limit=20")
      .then((response) => {
        if (!isActive) {
          return;
        }
        setData(
          response.data.filter(
            (confirmation) => confirmation.session_id === sessionId && confirmation.status === "pending",
          ),
        );
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
  }, [refreshNonce, sessionId]);

  return {
    data,
    isLoading,
    error,
    refresh: () => setRefreshNonce((value) => value + 1),
  };
}
