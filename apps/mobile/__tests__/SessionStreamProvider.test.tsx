import { act, render, screen, waitFor } from "@testing-library/react-native";
import { Text } from "react-native";

const SESSION_TITLE = "Demo Workgroup";

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
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close = jest.fn(() => {
    this.onclose?.();
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
    expect(MockWebSocket.instances[0]?.url).toContain("/api/v1/ws/sessions/sess_default?token=mock_owner_token");

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
});
