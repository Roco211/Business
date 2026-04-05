import { useState } from "react";

import { apiPostJson } from "../../../shared/api/client";


type ApproveConfirmationPayload = {
  item_name: string;
  quantity: number;
  unit: string;
  price: number;
};


type ApproveConfirmationResponse = {
  data: {
    confirmation_id: string;
    status: string;
  };
};


export function useApproveConfirmationMutation() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function approveConfirmation(
    confirmationId: string,
    fields: ApproveConfirmationPayload,
  ) {
    setIsSubmitting(true);
    setError(null);
    try {
      return await apiPostJson<ApproveConfirmationResponse, { fields: ApproveConfirmationPayload }>(
        `/api/v1/confirmations/${confirmationId}/approve`,
        { fields },
      );
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Failed to approve confirmation";
      setError(message);
      return null;
    } finally {
      setIsSubmitting(false);
    }
  }

  return {
    isSubmitting,
    error,
    approveConfirmation,
  };
}
