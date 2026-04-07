import { useEffect, useState } from "react";

import { apiPostJson } from "../api/client";
import { useAuthStoreState } from "../auth/authStore";


export type BootstrappedSession = {
  session_id: string;
  session_type: string;
  title: string;
  participants: string[];
};


type SessionBootstrapResponse = {
  data: BootstrappedSession;
};


export function useBootstrapSession() {
  const authStoreState = useAuthStoreState();
  const accessToken = authStoreState.session?.accessToken ?? null;
  const [data, setData] = useState<BootstrappedSession | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (accessToken === null) {
      setData(null);
      setError(null);
      setIsLoading(false);
      return;
    }

    let isActive = true;

    setIsLoading(true);
    setError(null);
    setData(null);

    apiPostJson<SessionBootstrapResponse, Record<string, never>>("/api/v1/sessions/bootstrap", {})
      .then((response) => {
        if (!isActive) {
          return;
        }
        setData(response.data);
      })
      .catch((reason: unknown) => {
        if (!isActive) {
          return;
        }
        setData(null);
        setError(reason instanceof Error ? reason.message : "Failed to bootstrap session");
      })
      .finally(() => {
        if (isActive) {
          setIsLoading(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, [accessToken]);

  return {
    data,
    isLoading,
    error,
  };
}
