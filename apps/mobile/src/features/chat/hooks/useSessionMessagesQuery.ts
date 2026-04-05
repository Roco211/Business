import { useEffect, useState } from "react";

import { apiGetJson } from "../../../shared/api/client";


export type SessionMessageRecord = {
  message_id: string;
  session_id: string;
  actor_type: string;
  actor_id: string;
  message_type: string;
  text: string | null;
  media_ids: string[];
  task_run_id: string | null;
  created_at: string;
};


type SessionMessagesResponse = {
  data: SessionMessageRecord[];
  meta: {
    next_cursor: string | null;
  };
};


export function useSessionMessagesQuery(sessionId: string | null) {
  const [data, setData] = useState<SessionMessageRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshNonce, setRefreshNonce] = useState(0);

  useEffect(() => {
    let isActive = true;

    if (sessionId === null) {
      setData([]);
      setError(null);
      setIsLoading(false);
      return () => {
        isActive = false;
      };
    }

    setIsLoading(true);
    setError(null);

    apiGetJson<SessionMessagesResponse>(`/api/v1/sessions/${sessionId}/messages?limit=20`)
      .then((response) => {
        if (!isActive) {
          return;
        }
        setData(
          [...response.data].sort(
            (left, right) => Date.parse(left.created_at) - Date.parse(right.created_at),
          ),
        );
      })
      .catch((reason: unknown) => {
        if (!isActive) {
          return;
        }
        setError(reason instanceof Error ? reason.message : "Failed to load chat messages");
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [refreshNonce, sessionId]);

  return {
    data,
    isLoading,
    error,
    refresh: () => setRefreshNonce((value) => value + 1),
  };
}
