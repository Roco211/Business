import { useState } from "react";

import { useCreateMediaUploadMutation } from "./useCreateMediaUploadMutation";
import { useCompleteMediaUploadMutation } from "./useCompleteMediaUploadMutation";
import { useSendMessageMutation } from "./useSendMessageMutation";
import { uploadDemoMedia } from "../utils/demoMediaUpload";

const DEMO_CONFIG = {
  query: {
    fileName: "photo-query-demo.jpg",
    caption: "check shelf stock for red bull",
    uploadBody: "photo-query-demo-bytes-check-shelf-stock-for-red-bull",
  },
  stock_in: {
    fileName: "photo-stock-in-demo.jpg",
    caption: "restock red bull cans",
    uploadBody: "photo-stock-in-demo-bytes-restock-red-bull-cans",
  },
} as const;

export function useSendImageDemoMutation(sessionId: string | null) {
  const createMediaUpload = useCreateMediaUploadMutation();
  const completeMediaUpload = useCompleteMediaUploadMutation();
  const sendMessage = useSendMessageMutation(sessionId);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  async function submitImageDemo(kind: keyof typeof DEMO_CONFIG) {
    const demo = DEMO_CONFIG[kind];
    setUploadError(null);
    setIsUploading(true);
    let mediaId: string | null = null;
    try {
      mediaId = await uploadDemoMedia({
        mediaType: "image",
        fileName: demo.fileName,
        contentType: "image/jpeg",
        body: demo.uploadBody,
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

    return await sendMessage.submitMessage(demo.caption, {
      message_type: "image",
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
    submitImageDemo,
  };
}
