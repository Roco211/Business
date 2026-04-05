import { act, render, screen, waitFor } from "@testing-library/react-native";
import { Text } from "react-native";

import { clearAuthSession, getAuthSession, setAuthSession } from "../src/shared/auth/authStore";

const SESSION_TITLE = "Demo Workgroup";
const TEST_ACCESS_TOKEN = "token_session_test";

type MockSessionStreamEvent = {
  event_id: string;
  seq: number;
  event_type: string;
  session_id: string;
  task_run_id: string | null;
  message_id: string | null;
  occurred_at: string;
  data: Record<string, unknown>;
};


class MockWebSocket {
  static instances: MockWebSocket[] = [];

  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: ((event: { code: number }) => void) | null = null;
  onerror: (() => void) | null = null;
  close = jest.fn(() => {
    this.onclose?.({ code: 1000 });
  });

  constructor(public readonly url: string) {
    MockWebSocket.instances.push(this);
  }

  emitOpen() {
    this.onopen?.();
  }

  emitMessage(event: MockSessionStreamEvent) {
    this.onmessage?.({ data: JSON.stringify(event) });
  }

  emitClose(code: number) {
    this.onclose?.({ code });
  }
}


function loadSessionStreamModules() {
  try {
    const providerModule = require("../src/shared/session/SessionStreamProvider");
    const hookModule = require("../src/shared/session/useSessionStream");
    return {
      SessionStreamProvider: providerModule.SessionStreamProvider as React.ComponentType<{
        children: React.ReactNode;
      }>,
      useSessionStream: hookModule.useSessionStream as () => {
        sessionId: string | null;
        sessionTitle: string | null;
        connectionState: string;
        lastEvent: MockSessionStreamEvent | null;
        recentEvents: MockSessionStreamEvent[];
      },
    };
  } catch (error) {
    throw new Error(`session stream modules missing: ${String(error)}`);
  }
}


describe("SessionStreamProvider", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    act(() => {
      setAuthSession({
        accessToken: TEST_ACCESS_TOKEN,
        tokenType: "Bearer",
        ownerActorId: "owner_default",
        shopId: "shop_default",
        shopName: "Demo Shop",
      });
    });
    global.WebSocket = MockWebSocket as unknown as typeof WebSocket;
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: {
          session_id: "sess_default",
          session_type: "workgroup",
          title: SESSION_TITLE,
          participants: ["xiaoya", "laoli"],
        },
      }),
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    act(() => {
      clearAuthSession();
    });
    jest.resetAllMocks();
  });

  it("bootstraps the default session and exposes websocket events", async () => {
    const { SessionStreamProvider, useSessionStream } = loadSessionStreamModules();

    function Consumer() {
      const stream = useSessionStream();
      return (
        <>
          <Text>{stream.sessionId ?? "no-session"}</Text>
          <Text>{stream.sessionTitle ?? "no-title"}</Text>
          <Text>{stream.connectionState}</Text>
          <Text>{stream.lastEvent?.event_type ?? "no-event"}</Text>
          <Text>{String(stream.recentEvents.length)}</Text>
        </>
      );
    }

    render(
      <SessionStreamProvider>
        <Consumer />
      </SessionStreamProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("sess_default")).toBeTruthy();
      expect(screen.getByText(SESSION_TITLE)).toBeTruthy();
    });

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0]?.url).toContain(`/api/v1/ws/sessions/sess_default?token=${TEST_ACCESS_TOKEN}`);

    act(() => {
      MockWebSocket.instances[0]?.emitOpen();
      MockWebSocket.instances[0]?.emitMessage({
        event_id: "evt_message_created",
        seq: 1,
        event_type: "message.created",
        session_id: "sess_default",
        task_run_id: "task_1",
        message_id: "msg_1",
        occurred_at: "2026-04-05T12:00:00.000Z",
        data: {
          preview_text: "restock cola",
        },
      });
    });

    await waitFor(() => {
      expect(screen.getByText("connected")).toBeTruthy();
      expect(screen.getByText("message.created")).toBeTruthy();
      expect(screen.getByText("1")).toBeTruthy();
    });
  });

  it("reconnects with the latest durable seq and ignores stale replay duplicates", async () => {
    jest.useFakeTimers();
    const { SessionStreamProvider, useSessionStream } = loadSessionStreamModules();

    function Consumer() {
      const stream = useSessionStream();
      return (
        <>
          <Text>{stream.sessionId ?? "no-session"}</Text>
          <Text>{stream.connectionState}</Text>
          <Text>{stream.lastEvent?.event_id ?? "no-event-id"}</Text>
          <Text>{String(stream.recentEvents.length)}</Text>
        </>
      );
    }

    render(
      <SessionStreamProvider>
        <Consumer />
      </SessionStreamProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("sess_default")).toBeTruthy();
    });

    act(() => {
      MockWebSocket.instances[0]?.emitOpen();
      MockWebSocket.instances[0]?.emitMessage({
        event_id: "evt_message_created_1",
        seq: 1,
        event_type: "message.created",
        session_id: "sess_default",
        task_run_id: "task_1",
        message_id: "msg_1",
        occurred_at: "2026-04-05T12:00:00.000Z",
        data: {
          preview_text: "restock cola",
        },
      });
    });

    await waitFor(() => {
      expect(screen.getByText("evt_message_created_1")).toBeTruthy();
      expect(screen.getByText("1")).toBeTruthy();
    });

    act(() => {
      MockWebSocket.instances[0]?.close();
      jest.advanceTimersByTime(1000);
    });

    expect(MockWebSocket.instances).toHaveLength(2);
    expect(MockWebSocket.instances[1]?.url).toContain("after_seq=1");

    act(() => {
      MockWebSocket.instances[1]?.emitOpen();
      MockWebSocket.instances[1]?.emitMessage({
        event_id: "evt_message_created_1_replay",
        seq: 1,
        event_type: "message.created",
        session_id: "sess_default",
        task_run_id: "task_1",
        message_id: "msg_1",
        occurred_at: "2026-04-05T12:00:05.000Z",
        data: {
          preview_text: "restock cola",
        },
      });
    });

    await waitFor(() => {
      expect(screen.getByText("evt_message_created_1")).toBeTruthy();
      expect(screen.getByText("1")).toBeTruthy();
    });

    jest.useRealTimers();
  });

  it("reconnects from seq 0 after a local demo reset clears the durable cursor", async () => {
    const { SessionStreamProvider, useSessionStream } = loadSessionStreamModules();
    let latestNotifyDemoReset: (() => void) | null = null;

    function Consumer() {
      const stream = useSessionStream();
      latestNotifyDemoReset = stream.notifyDemoDataReset;
      return (
        <>
          <Text>{stream.sessionId ?? "no-session"}</Text>
          <Text>{stream.lastEvent?.event_id ?? "no-event-id"}</Text>
          <Text>{String(stream.recentEvents.length)}</Text>
        </>
      );
    }

    render(
      <SessionStreamProvider>
        <Consumer />
      </SessionStreamProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("sess_default")).toBeTruthy();
    });

    act(() => {
      MockWebSocket.instances[0]?.emitOpen();
      MockWebSocket.instances[0]?.emitMessage({
        event_id: "evt_message_created_1",
        seq: 1,
        event_type: "message.created",
        session_id: "sess_default",
        task_run_id: "task_1",
        message_id: "msg_1",
        occurred_at: "2026-04-05T12:00:00.000Z",
        data: {
          preview_text: "restock cola",
        },
      });
    });

    await waitFor(() => {
      expect(screen.getByText("evt_message_created_1")).toBeTruthy();
      expect(screen.getByText("1")).toBeTruthy();
    });

    act(() => {
      latestNotifyDemoReset?.();
    });

    expect(MockWebSocket.instances).toHaveLength(2);
    expect(MockWebSocket.instances[1]?.url).not.toContain("after_seq=1");
  });

  it("clears auth and stops reconnect when websocket closes with code 4401", async () => {
    jest.useFakeTimers();
    const { SessionStreamProvider } = loadSessionStreamModules();

    render(
      <SessionStreamProvider>
        <Text>Session Consumer</Text>
      </SessionStreamProvider>,
    );

    await waitFor(() => {
      expect(MockWebSocket.instances).toHaveLength(1);
    });

    act(() => {
      MockWebSocket.instances[0]?.emitOpen();
      MockWebSocket.instances[0]?.emitClose(4401);
      jest.advanceTimersByTime(10_000);
    });

    expect(getAuthSession()).toBeNull();
    expect(MockWebSocket.instances).toHaveLength(1);
    jest.useRealTimers();
  });
});
