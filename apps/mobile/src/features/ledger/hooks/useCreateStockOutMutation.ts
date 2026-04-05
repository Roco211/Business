import { useState } from "react";

import { apiPostJson } from "../../../shared/api/client";


type CreateStockOutResponse = {
  data: {
    stock_out_event_id: string;
    item_id: string;
    new_quantity: string;
  };
};


type CreateStockOutInput = {
  item_id: string;
  expected_quantity: number;
  stock_out_quantity: number;
  reason: string;
};


export function useCreateStockOutMutation() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submitStockOut(input: CreateStockOutInput) {
    setIsSubmitting(true);
    setError(null);
    try {
      return await apiPostJson<CreateStockOutResponse, CreateStockOutInput>(
        "/api/v1/inventory-events/stock-out",
        input,
      );
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Failed to submit stock-out";
      setError(message);
      return null;
    } finally {
      setIsSubmitting(false);
    }
  }

  return {
    isSubmitting,
    error,
    submitStockOut,
  };
}
