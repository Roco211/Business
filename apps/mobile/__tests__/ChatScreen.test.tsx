import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import ChatScreen from "../src/features/chat/screens/ChatScreen";


let mockLastChatEvent: {
  event_id: string;
  seq: number;
  event_type: string;
  session_id: string;
  task_run_id: string | null;
  message_id: string | null;
  occurred_at: string;
  data: Record<string, unknown>;
} | null = null;


jest.mock("../src/shared/session/useSessionStream", () => ({
  useSessionStream: () => ({
    sessionId: "sess_default",
    sessionTitle: "数字员工工作群",
    connectionState: "connected",
    bootstrapError: null,
    lastEvent: mockLastChatEvent,
    recentEvents: mockLastChatEvent === null ? [] : [mockLastChatEvent],
  }),
}));


describe("ChatScreen", () => {
  beforeEach(() => {
    mockLastChatEvent = null;

    const messages = [
      {
        message_id: "msg_owner_1",
        session_id: "sess_default",
        actor_type: "owner",
        actor_id: "owner_default",
        message_type: "text",
        text: "restock cola",
        media_ids: [],
        task_run_id: "task_1",
        created_at: "2026-04-05T12:00:00.000Z",
      },
      {
        message_id: "msg_system_1",
        session_id: "sess_default",
        actor_type: "system",
        actor_id: "runtime",
        message_type: "text",
        text: "Mock runtime: please confirm the stock-in details before commit.",
        media_ids: [],
        task_run_id: "task_1",
        created_at: "2026-04-05T12:00:03.000Z",
      },
    ];

    global.fetch = jest.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url.includes("/api/v1/sessions/sess_default/messages") && method === "POST") {
        const payload = JSON.parse(String(init?.body ?? "{}")) as {
          text?: string;
        };
        messages.push({
          message_id: "msg_owner_2",
          session_id: "sess_default",
          actor_type: "owner",
          actor_id: "owner_default",
          message_type: "text",
          text: payload.text ?? "",
          media_ids: [],
          task_run_id: "task_2",
          created_at: "2026-04-05T12:05:00.000Z",
        });
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: {
              message_id: "msg_owner_2",
              task_run_id: "task_2",
              status: "created",
            },
          }),
        });
      }

      if (url.includes("/api/v1/sessions/sess_default/messages")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: messages,
            meta: {
              next_cursor: null,
            },
          }),
        });
      }

      if (url.includes("/api/v1/confirmations?status=pending&limit=20")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: [],
            meta: {
              count: 0,
            },
          }),
        });
      }

      return Promise.resolve({
        ok: false,
        json: async () => ({
          error: {
            code: "unexpected_request",
            message: "Unexpected request",
            details: [],
          },
        }),
      });
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  it("renders durable session messages instead of only recent session events", async () => {
    render(<ChatScreen />);

    expect(screen.getByText("Loading chat...")).toBeTruthy();

    await waitFor(() => {
      expect(screen.getByText("数字员工工作群")).toBeTruthy();
      expect(screen.getByText("connected")).toBeTruthy();
      expect(screen.getByText("restock cola")).toBeTruthy();
      expect(
        screen.getByText("Mock runtime: please confirm the stock-in details before commit."),
      ).toBeTruthy();
    });
  });

  it("submits a text message and refreshes the timeline", async () => {
    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.getByText("restock cola")).toBeTruthy();
    });

    fireEvent.changeText(screen.getByPlaceholderText("Type a message"), "Count chips too");
    fireEvent.press(screen.getByText("Send"));

    await waitFor(() => {
      expect(screen.getByText("Count chips too")).toBeTruthy();
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/sessions/sess_default/messages"),
        expect.objectContaining({
          method: "POST",
        }),
      );
    });
  });
});
