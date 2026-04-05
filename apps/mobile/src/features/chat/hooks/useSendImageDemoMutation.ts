import { useCreateMediaUploadMutation } from "./useCreateMediaUploadMutation";
import { useCompleteMediaUploadMutation } from "./useCompleteMediaUploadMutation";
import { useSendMessageMutation } from "./useSendMessageMutation";

const DEMO_CONFIG = {
  query: {
    fileName: "photo-query-demo.jpg",
    caption: "check shelf stock for red bull",
    checksum: "photo-query-demo-checksum",
  },
  stock_in: {
    fileName: "photo-stock-in-demo.jpg",
    caption: "restock red bull cans",
    checksum: "photo-stock-in-demo-checksum",
  },
} as const;

export function useSendImageDemoMutation(sessionId: string | null) {
  const createMediaUpload = useCreateMediaUploadMutation();
  const completeMediaUpload = useCompleteMediaUploadMutation();
  const sendMessage = useSendMessageMutation(sessionId);

  async function submitImageDemo(kind: keyof typeof DEMO_CONFIG) {
    const demo = DEMO_CONFIG[kind];
    const createdUpload = await createMediaUpload.createMediaUpload({
      media_type: "image",
      file_name: demo.fileName,
      content_type: "image/jpeg",
      size_bytes: 2048,
    });
    if (createdUpload === null) {
      return null;
    }

    const completedUpload = await completeMediaUpload.completeMediaUpload(createdUpload.data.media_id, {
      checksum_sha256: demo.checksum,
      size_bytes: 2048,
    });
    if (completedUpload === null) {
      return null;
    }

    return await sendMessage.submitMessage(demo.caption, {
      message_type: "image",
      media_ids: [createdUpload.data.media_id],
    });
  }

  return {
    isSubmitting:
      createMediaUpload.isSubmitting || completeMediaUpload.isSubmitting || sendMessage.isSubmitting,
    error: createMediaUpload.error ?? completeMediaUpload.error ?? sendMessage.error,
    submitImageDemo,
  };
}
