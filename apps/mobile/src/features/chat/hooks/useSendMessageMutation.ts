import { useState } from "react";

import { apiPostJson } from "../../../shared/api/client";


type CreateSessionMessageResponse = {
  data: {
    message_id: string;
    task_run_id: string;
    status: string;
  };
};


type CreateSessionMessageRequest = {
  message_type: string;
  text: string;
  media_ids: string[];
  client_request_id: string;
};


type SubmitMessageOptions = {
  message_type?: string;
  media_ids?: string[];
};


function createClientRequestId() {
  return `chat_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}


export function useSendMessageMutation(sessionId: string | null) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submitMessage(text: string, options?: SubmitMessageOptions) {
    const trimmedText = text.trim();
    if (sessionId === null || trimmedText.length === 0) {
      return null;
    }

    setIsSubmitting(true);
    setError(null);
    try {
      return await apiPostJson<CreateSessionMessageResponse, CreateSessionMessageRequest>(
        `/api/v1/sessions/${sessionId}/messages`,
        {
          message_type: options?.message_type ?? "text",
          text: trimmedText,
          media_ids: options?.media_ids ?? [],
          client_request_id: createClientRequestId(),
        },
      );
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Failed to send chat message";
      setError(message);
      return null;
    } finally {
      setIsSubmitting(false);
    }
  }

  return {
    isSubmitting,
    error,
    submitMessage,
  };
}
