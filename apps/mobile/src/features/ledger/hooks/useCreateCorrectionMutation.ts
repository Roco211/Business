import { useState } from "react";

import { apiPostJson } from "../../../shared/api/client";


type CreateCorrectionResponse = {
  data: {
    correction_event_id: string;
    item_id: string;
    new_quantity: string;
  };
};


type CreateCorrectionInput = {
  item_id: string;
  corrected_quantity: number;
  reason: string;
};


export function useCreateCorrectionMutation() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submitCorrection(input: CreateCorrectionInput) {
    setIsSubmitting(true);
    setError(null);
    try {
      return await apiPostJson<CreateCorrectionResponse, CreateCorrectionInput>(
        "/api/v1/inventory-events/corrections",
        input,
      );
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Failed to submit correction";
      setError(message);
      throw reason;
    } finally {
      setIsSubmitting(false);
    }
  }

  return {
    isSubmitting,
    error,
    submitCorrection,
  };
}
