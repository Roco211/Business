import { useCreateMediaUploadMutation } from "./useCreateMediaUploadMutation";
import { useCompleteMediaUploadMutation } from "./useCompleteMediaUploadMutation";
import { useSendMessageMutation } from "./useSendMessageMutation";

const DEMO_CONFIG = {
  fileName: "receipt-demo.jpg",
  caption: "receipt scan today",
  checksum: "receipt-demo-checksum",
} as const;

export function useSendReceiptDemoMutation(sessionId: string | null) {
  const createMediaUpload = useCreateMediaUploadMutation();
  const completeMediaUpload = useCompleteMediaUploadMutation();
  const sendMessage = useSendMessageMutation(sessionId);

  async function submitReceiptDemo() {
    const createdUpload = await createMediaUpload.createMediaUpload({
      media_type: "receipt-image",
      file_name: DEMO_CONFIG.fileName,
      content_type: "image/jpeg",
      size_bytes: 2048,
    });
    if (createdUpload === null) {
      return null;
    }

    const completedUpload = await completeMediaUpload.completeMediaUpload(createdUpload.data.media_id, {
      checksum_sha256: DEMO_CONFIG.checksum,
      size_bytes: 2048,
    });
    if (completedUpload === null) {
      return null;
    }

    return await sendMessage.submitMessage(DEMO_CONFIG.caption, {
      message_type: "receipt-image",
      media_ids: [createdUpload.data.media_id],
    });
  }

  return {
    isSubmitting:
      createMediaUpload.isSubmitting || completeMediaUpload.isSubmitting || sendMessage.isSubmitting,
    error: createMediaUpload.error ?? completeMediaUpload.error ?? sendMessage.error,
    submitReceiptDemo,
  };
}
