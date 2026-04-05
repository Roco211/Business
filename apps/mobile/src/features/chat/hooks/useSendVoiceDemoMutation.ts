import { useCreateMediaUploadMutation } from "./useCreateMediaUploadMutation";
import { useCompleteMediaUploadMutation } from "./useCompleteMediaUploadMutation";
import { useSendMessageMutation } from "./useSendMessageMutation";


const DEMO_CONFIG = {
  query: {
    fileName: "voice-query-demo.m4a",
    transcript: "check stock left for cola",
    checksum: "voice-query-demo-checksum",
  },
  stock_in: {
    fileName: "voice-stock-in-demo.m4a",
    transcript: "restock apples today",
    checksum: "voice-stock-in-demo-checksum",
  },
  stock_out: {
    fileName: "voice-stock-out-demo.m4a",
    transcript: "stock out cola for walk in sale",
    checksum: "voice-stock-out-demo-checksum",
  },
} as const;


export function useSendVoiceDemoMutation(sessionId: string | null) {
  const createMediaUpload = useCreateMediaUploadMutation();
  const completeMediaUpload = useCompleteMediaUploadMutation();
  const sendMessage = useSendMessageMutation(sessionId);

  async function submitVoiceDemo(kind: keyof typeof DEMO_CONFIG) {
    const demo = DEMO_CONFIG[kind];
    const createdUpload = await createMediaUpload.createMediaUpload({
      media_type: "audio",
      file_name: demo.fileName,
      content_type: "audio/m4a",
      size_bytes: 1024,
    });
    if (createdUpload === null) {
      return null;
    }

    const completedUpload = await completeMediaUpload.completeMediaUpload(createdUpload.data.media_id, {
      checksum_sha256: demo.checksum,
      size_bytes: 1024,
    });
    if (completedUpload === null) {
      return null;
    }

    return await sendMessage.submitMessage(demo.transcript, {
      message_type: "voice",
      media_ids: [createdUpload.data.media_id],
    });
  }

  return {
    isSubmitting:
      createMediaUpload.isSubmitting || completeMediaUpload.isSubmitting || sendMessage.isSubmitting,
    error: createMediaUpload.error ?? completeMediaUpload.error ?? sendMessage.error,
    submitVoiceDemo,
  };
}
