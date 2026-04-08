import { useState } from "react";

import { useCreateMediaUploadMutation } from "./useCreateMediaUploadMutation";
import { useCompleteMediaUploadMutation } from "./useCompleteMediaUploadMutation";
import { useSendMessageMutation } from "./useSendMessageMutation";
import { uploadDemoMedia } from "../utils/demoMediaUpload";


const DEMO_CONFIG = {
  query: {
    fileName: "voice-query-demo.m4a",
    transcript: "check stock left for cola",
    uploadBody: "voice-query-demo-bytes-check-stock-left-for-cola",
  },
  stock_in: {
    fileName: "voice-stock-in-demo.m4a",
    transcript: "restock apples today",
    uploadBody: "voice-stock-in-demo-bytes-restock-apples-today",
  },
  stock_out: {
    fileName: "voice-stock-out-demo.m4a",
    transcript: "stock out cola for walk in sale",
    uploadBody: "voice-stock-out-demo-bytes-stock-out-cola-for-walk-in-sale",
  },
} as const;


export function useSendVoiceDemoMutation(sessionId: string | null) {
  const createMediaUpload = useCreateMediaUploadMutation();
  const completeMediaUpload = useCompleteMediaUploadMutation();
  const sendMessage = useSendMessageMutation(sessionId);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  async function submitVoiceDemo(kind: keyof typeof DEMO_CONFIG) {
    const demo = DEMO_CONFIG[kind];
    setUploadError(null);
    setIsUploading(true);
    let mediaId: string | null = null;
    try {
      mediaId = await uploadDemoMedia({
        mediaType: "audio",
        fileName: demo.fileName,
        contentType: "audio/m4a",
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

    return await sendMessage.submitMessage(demo.transcript, {
      message_type: "voice",
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
    submitVoiceDemo,
  };
}
