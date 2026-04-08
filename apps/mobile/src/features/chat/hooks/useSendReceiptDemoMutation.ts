import { useState } from "react";

import { useCreateMediaUploadMutation } from "./useCreateMediaUploadMutation";
import { useCompleteMediaUploadMutation } from "./useCompleteMediaUploadMutation";
import { useSendMessageMutation } from "./useSendMessageMutation";
import { uploadDemoMedia } from "../utils/demoMediaUpload";

const DEMO_CONFIG = {
  fileName: "receipt-demo.jpg",
  caption: "receipt scan today",
  uploadBody: "receipt-demo-bytes-receipt-scan-today",
} as const;

export function useSendReceiptDemoMutation(sessionId: string | null) {
  const createMediaUpload = useCreateMediaUploadMutation();
  const completeMediaUpload = useCompleteMediaUploadMutation();
  const sendMessage = useSendMessageMutation(sessionId);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  async function submitReceiptDemo() {
    setUploadError(null);
    setIsUploading(true);
    let mediaId: string | null = null;
    try {
      mediaId = await uploadDemoMedia({
        mediaType: "receipt-image",
        fileName: DEMO_CONFIG.fileName,
        contentType: "image/jpeg",
        body: DEMO_CONFIG.uploadBody,
        createMediaUpload: createMediaUpload.createMediaUpload,
        completeMediaUpload: completeMediaUpload.completeMediaUpload,
        onUploadError: setUploadError,
      });
    } finally {
      setIsUploading(false);
    }
    if (mediaId === null) {
      return null;
    }

    return await sendMessage.submitMessage(DEMO_CONFIG.caption, {
      message_type: "receipt-image",
      media_ids: [mediaId],
    });
  }

  return {
    isSubmitting:
      isUploading
      || createMediaUpload.isSubmitting
      || completeMediaUpload.isSubmitting
      || sendMessage.isSubmitting,
    error: uploadError ?? createMediaUpload.error ?? completeMediaUpload.error ?? sendMessage.error,
    submitReceiptDemo,
  };
}
