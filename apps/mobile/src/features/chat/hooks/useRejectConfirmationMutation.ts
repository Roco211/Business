import { useState } from "react";

import { apiPostJson } from "../../../shared/api/client";


type RejectConfirmationResponse = {
  data: {
    confirmation_id: string;
    status: string;
  };
};


export function useRejectConfirmationMutation() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function rejectConfirmation(confirmationId: string) {
    setIsSubmitting(true);
    setError(null);
    try {
      return await apiPostJson<RejectConfirmationResponse, Record<string, never>>(
        `/api/v1/confirmations/${confirmationId}/reject`,
        {},
      );
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Failed to reject confirmation";
      setError(message);
      return null;
    } finally {
      setIsSubmitting(false);
    }
  }

  return {
    isSubmitting,
    error,
    rejectConfirmation,
  };
}
