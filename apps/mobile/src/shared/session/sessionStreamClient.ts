import { getApiBaseUrl } from "../api/client";


const DEFAULT_OWNER_TOKEN = "mock_owner_token";
const RECONNECT_DELAYS_MS = [1000, 2000, 5000, 10000];


export type SessionStreamEvent = {
  event_id: string;
  seq: number;
  event_type: string;
  session_id: string;
  task_run_id: string | null;
  message_id: string | null;
  occurred_at: string;
  data: Record<string, unknown>;
};


export type SessionStreamConnectionState =
  | "idle"
  | "bootstrapping"
  | "connecting"
  | "connected"
  | "disconnected"
  | "error";


type CreateSessionStreamClientOptions = {
  sessionId: string;
  onEvent: (event: SessionStreamEvent) => void;
  onConnectionStateChange: (state: SessionStreamConnectionState) => void;
};


function buildSessionStreamUrl(sessionId: string): string {
  const baseUrl = getApiBaseUrl();
  const websocketBaseUrl = baseUrl.startsWith("https://")
    ? baseUrl.replace("https://", "wss://")
    : baseUrl.replace("http://", "ws://");
  return `${websocketBaseUrl}/api/v1/ws/sessions/${sessionId}?token=${DEFAULT_OWNER_TOKEN}`;
}


function parseSessionStreamEvent(messageData: string): SessionStreamEvent | null {
  try {
    const parsed = JSON.parse(messageData) as SessionStreamEvent;
    if (!parsed.event_id || !parsed.event_type || !parsed.session_id) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}


export function createSessionStreamClient(options: CreateSessionStreamClientOptions) {
  let websocket: WebSocket | null = null;
  let reconnectAttempt = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let disposed = false;

  function clearReconnectTimer() {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  }

  function scheduleReconnect() {
    clearReconnectTimer();
    const delay = RECONNECT_DELAYS_MS[Math.min(reconnectAttempt, RECONNECT_DELAYS_MS.length - 1)];
    reconnectAttempt += 1;
    reconnectTimer = setTimeout(connect, delay);
  }

  function connect() {
    if (disposed) {
      return;
    }

    options.onConnectionStateChange("connecting");
    websocket = new WebSocket(buildSessionStreamUrl(options.sessionId));

    websocket.onopen = () => {
      reconnectAttempt = 0;
      options.onConnectionStateChange("connected");
    };

    websocket.onmessage = (messageEvent) => {
      const event = parseSessionStreamEvent(String(messageEvent.data));
      if (event === null) {
        return;
      }
      options.onEvent(event);
    };

    websocket.onerror = () => {
      options.onConnectionStateChange("error");
    };

    websocket.onclose = () => {
      options.onConnectionStateChange("disconnected");
      if (disposed) {
        return;
      }
      scheduleReconnect();
    };
  }

  connect();

  return {
    disconnect() {
      disposed = true;
      clearReconnectTimer();
      websocket?.close();
      websocket = null;
    },
  };
}
