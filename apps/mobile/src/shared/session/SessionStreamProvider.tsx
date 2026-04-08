import { createContext, startTransition, useEffect, useRef, useState } from "react";

import {
  createSessionStreamClient,
  SessionStreamConnectionState,
  SessionStreamEvent,
} from "./sessionStreamClient";
import { useBootstrapSession } from "./useBootstrapSession";


type SessionStreamContextValue = {
  sessionId: string | null;
  sessionTitle: string | null;
  connectionState: SessionStreamConnectionState;
  bootstrapError: string | null;
  retryBootstrap: () => void;
  lastEvent: SessionStreamEvent | null;
  recentEvents: SessionStreamEvent[];
  dataResetVersion: number;
  notifyDemoDataReset: () => void;
};


const DEFAULT_CONTEXT_VALUE: SessionStreamContextValue = {
  sessionId: null,
  sessionTitle: null,
  connectionState: "idle",
  bootstrapError: null,
  retryBootstrap: () => undefined,
  lastEvent: null,
  recentEvents: [],
  dataResetVersion: 0,
  notifyDemoDataReset: () => undefined,
};


export const SessionStreamContext = createContext<SessionStreamContextValue>(DEFAULT_CONTEXT_VALUE);


export function SessionStreamProvider({ children }: { children: React.ReactNode }) {
  const bootstrap = useBootstrapSession();
  const [connectionState, setConnectionState] = useState<SessionStreamConnectionState>("bootstrapping");
  const [lastEvent, setLastEvent] = useState<SessionStreamEvent | null>(null);
  const [recentEvents, setRecentEvents] = useState<SessionStreamEvent[]>([]);
  const [dataResetVersion, setDataResetVersion] = useState(0);
  const lastBusinessSeqRef = useRef(0);

  function notifyDemoDataReset() {
    lastBusinessSeqRef.current = 0;
    startTransition(() => {
      setLastEvent(null);
      setRecentEvents([]);
      setDataResetVersion((current) => current + 1);
    });
  }

  useEffect(() => {
    if (bootstrap.isLoading) {
      setConnectionState("bootstrapping");
      return;
    }

    if (bootstrap.error) {
      startTransition(() => {
        setLastEvent(null);
        setRecentEvents([]);
      });
      setConnectionState("error");
      return;
    }

    if (bootstrap.data === null) {
      startTransition(() => {
        setLastEvent(null);
        setRecentEvents([]);
      });
      setConnectionState("idle");
      return;
    }

    setConnectionState("connecting");
    const client = createSessionStreamClient({
      sessionId: bootstrap.data.session_id,
      getAfterSeq: () => lastBusinessSeqRef.current,
      onConnectionStateChange: setConnectionState,
      onEvent: (event) => {
        const isTransportEvent = event.event_type === "session.ready" || event.event_type === "stream.keepalive";
        if (!isTransportEvent && event.seq <= lastBusinessSeqRef.current) {
          return;
        }
        if (!isTransportEvent) {
          lastBusinessSeqRef.current = event.seq;
        }
        if (event.event_type === "stream.keepalive") {
          return;
        }
        startTransition(() => {
          setLastEvent(event);
          setRecentEvents((current) => [event, ...current].slice(0, 10));
        });
      },
    });

    return () => {
      client.disconnect();
    };
  }, [bootstrap.data, bootstrap.error, bootstrap.isLoading, dataResetVersion]);

  return (
    <SessionStreamContext.Provider
      value={{
        sessionId: bootstrap.data?.session_id ?? null,
        sessionTitle: bootstrap.data?.title ?? null,
        connectionState,
        bootstrapError: bootstrap.error,
        retryBootstrap: bootstrap.retryBootstrap,
        lastEvent,
        recentEvents,
        dataResetVersion,
        notifyDemoDataReset,
      }}
    >
      {children}
    </SessionStreamContext.Provider>
  );
}
