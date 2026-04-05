import { useState } from "react";

import { apiPostJson } from "../../../shared/api/client";


type CreateMediaUploadRequest = {
  media_type: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
};


type CreateMediaUploadResponse = {
  data: {
    media_id: string;
    upload_url: string;
    public_url: string;
  };
};


export function useCreateMediaUploadMutation() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function createMediaUpload(input: CreateMediaUploadRequest) {
    setIsSubmitting(true);
    setError(null);
    try {
      return await apiPostJson<CreateMediaUploadResponse, CreateMediaUploadRequest>(
        "/api/v1/media-uploads",
        input,
      );
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Failed to create media upload";
      setError(message);
      return null;
    } finally {
      setIsSubmitting(false);
    }
  }

  return {
    isSubmitting,
    error,
    createMediaUpload,
  };
}
