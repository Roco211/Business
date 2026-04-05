import { useState } from "react";

import { apiPostJson } from "../../../shared/api/client";


type CompleteMediaUploadRequest = {
  checksum_sha256: string;
  size_bytes: number;
};


type CompleteMediaUploadResponse = {
  data: {
    media_id: string;
    status: string;
  };
};


export function useCompleteMediaUploadMutation() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function completeMediaUpload(mediaId: string, input: CompleteMediaUploadRequest) {
    setIsSubmitting(true);
    setError(null);
    try {
      return await apiPostJson<CompleteMediaUploadResponse, CompleteMediaUploadRequest>(
        `/api/v1/media-uploads/${mediaId}/complete`,
        input,
      );
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Failed to complete media upload";
      setError(message);
      return null;
    } finally {
      setIsSubmitting(false);
    }
  }

  return {
    isSubmitting,
    error,
    completeMediaUpload,
  };
}
