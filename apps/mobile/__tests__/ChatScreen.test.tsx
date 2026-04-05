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
let approvalShouldFail = false;
let rejectShouldFail = false;
let messagePostShouldFail = false;
let mediaUploadCreateShouldFail = false;
let mediaUploadCompleteShouldFail = false;
let messageRequestCount = 0;
let confirmationRequestCount = 0;
let mediaUploadRequestCount = 0;
let mediaUploadCompleteCount = 0;


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
    approvalShouldFail = false;
    rejectShouldFail = false;
    messagePostShouldFail = false;
    mediaUploadCreateShouldFail = false;
    mediaUploadCompleteShouldFail = false;
    messageRequestCount = 0;
    confirmationRequestCount = 0;
    mediaUploadRequestCount = 0;
    mediaUploadCompleteCount = 0;

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
    const pendingConfirmations = [
      {
        confirmation_id: "conf_1",
        session_id: "sess_default",
        task_run_id: "task_1",
        confirmation_type: "low-confidence-recognition",
        status: "pending",
        fields: {
          summary: "Please confirm the stock-in details before commit.",
          transcript: "restock cola",
          draft_fields: {
            item_name: "Cola",
            quantity: 3,
            unit: "box",
            price: 18.5,
          },
          required_fields: ["item_name", "quantity", "unit", "price"],
        },
        requested_by_employee_id: "emp_mock",
        resolution_payload: null,
        approved_by_actor_id: null,
        created_at: "2026-04-05T12:00:04.000Z",
        resolved_at: null,
      },
    ];

    global.fetch = jest.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";

      if (url.includes("/api/v1/media-uploads/") && url.includes("/complete") && method === "POST") {
        mediaUploadCompleteCount += 1;
        if (mediaUploadCompleteShouldFail) {
          return Promise.resolve({
            ok: false,
            json: async () => ({
              error: {
                code: "media_upload_conflict",
                message: "Media upload cannot transition from its current status",
                details: [],
              },
            }),
          });
        }
        const mediaId = url.split("/api/v1/media-uploads/")[1]?.replace("/complete", "") ?? "media_demo";
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: {
              media_id: mediaId,
              status: "uploaded",
            },
          }),
        });
      }

      if (url.includes("/api/v1/media-uploads") && method === "POST") {
        mediaUploadRequestCount += 1;
        if (mediaUploadCreateShouldFail) {
          return Promise.resolve({
            ok: false,
            json: async () => ({
              error: {
                code: "validation_error",
                message: "size_bytes must be greater than 0",
                details: [],
              },
            }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: {
              media_id: "media_voice_demo_1",
              upload_url: "https://mock.example/uploads/media_voice_demo_1",
              public_url: "https://mock.example/media/media_voice_demo_1",
            },
          }),
        });
      }

      if (url.includes("/api/v1/confirmations/conf_1/approve") && method === "POST") {
        if (approvalShouldFail) {
          return Promise.resolve({
            ok: false,
            json: async () => ({
              error: {
                code: "confirmation_fields_invalid",
                message: "item_name is required",
                details: [],
              },
            }),
          });
        }
        pendingConfirmations.splice(0, 1);
        messages.push({
          message_id: "msg_system_approved",
          session_id: "sess_default",
          actor_type: "system",
          actor_id: "runtime",
          message_type: "text",
          text: "Mock runtime: approved stock-in committed to inventory.",
          media_ids: [],
          task_run_id: "task_1",
          created_at: "2026-04-05T12:00:06.000Z",
        });
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: {
              confirmation_id: "conf_1",
              session_id: "sess_default",
              task_run_id: "task_1",
              confirmation_type: "low-confidence-recognition",
              status: "approved",
              fields: {
                summary: "Please confirm the stock-in details before commit.",
              },
              requested_by_employee_id: "emp_mock",
              resolution_payload: {
                fields: {
                  item_name: "Cola",
                  quantity: 3,
                  unit: "box",
                  price: 18.5,
                },
              },
              approved_by_actor_id: "owner_default",
              created_at: "2026-04-05T12:00:04.000Z",
              resolved_at: "2026-04-05T12:00:06.000Z",
            },
          }),
        });
      }

      if (url.includes("/api/v1/confirmations/conf_1/reject") && method === "POST") {
        if (rejectShouldFail) {
          return Promise.resolve({
            ok: false,
            json: async () => ({
              error: {
                code: "confirmation_not_pending",
                message: "Confirmation is not pending",
                details: [],
              },
            }),
          });
        }
        pendingConfirmations.splice(0, 1);
        messages.push({
          message_id: "msg_system_rejected",
          session_id: "sess_default",
          actor_type: "system",
          actor_id: "runtime",
          message_type: "text",
          text: "Mock runtime: owner rejected the confirmation and the stock-in task was rejected.",
          media_ids: [],
          task_run_id: "task_1",
          created_at: "2026-04-05T12:00:06.000Z",
        });
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: {
              confirmation_id: "conf_1",
              session_id: "sess_default",
              task_run_id: "task_1",
              confirmation_type: "low-confidence-recognition",
              status: "rejected",
              fields: {
                summary: "Please confirm the stock-in details before commit.",
              },
              requested_by_employee_id: "emp_mock",
              resolution_payload: null,
              approved_by_actor_id: null,
              created_at: "2026-04-05T12:00:04.000Z",
              resolved_at: "2026-04-05T12:00:06.000Z",
            },
          }),
        });
      }

      if (url.includes("/api/v1/sessions/sess_default/messages") && method === "POST") {
        if (messagePostShouldFail) {
          return Promise.resolve({
            ok: false,
            json: async () => ({
              error: {
                code: "validation_error",
                message: "Message text is required",
                details: [],
              },
            }),
          });
        }
        const payload = JSON.parse(String(init?.body ?? "{}")) as {
          text?: string;
          message_type?: string;
          media_ids?: string[];
        };
        messages.push({
          message_id: payload.message_type === "voice" ? "msg_voice_demo_1" : "msg_owner_2",
          session_id: "sess_default",
          actor_type: "owner",
          actor_id: "owner_default",
          message_type: payload.message_type ?? "text",
          text: payload.text ?? "",
          media_ids: payload.media_ids ?? [],
          task_run_id: payload.message_type === "voice" ? "task_voice_1" : "task_2",
          created_at: "2026-04-05T12:05:00.000Z",
        });
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: {
              message_id: payload.message_type === "voice" ? "msg_voice_demo_1" : "msg_owner_2",
              task_run_id: payload.message_type === "voice" ? "task_voice_1" : "task_2",
              status: "created",
            },
          }),
        });
      }

      if (url.includes("/api/v1/sessions/sess_default/messages")) {
        messageRequestCount += 1;
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
        confirmationRequestCount += 1;
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: pendingConfirmations,
            meta: {
              count: pendingConfirmations.length,
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
      expect(screen.getAllByText("restock cola").length).toBeGreaterThan(0);
      expect(
        screen.getByText("Mock runtime: please confirm the stock-in details before commit."),
      ).toBeTruthy();
    });
  });

  it("submits a text message and refreshes the timeline", async () => {
    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.getAllByText("restock cola").length).toBeGreaterThan(0);
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

  it("renders a pending stock-in confirmation card and approves it from chat", async () => {
    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.getByText("Pending confirmation")).toBeTruthy();
      expect(screen.getByDisplayValue("Cola")).toBeTruthy();
      expect(screen.getByDisplayValue("3")).toBeTruthy();
    });

    fireEvent.press(screen.getByText("Approve"));

    await waitFor(() => {
      expect(screen.queryByText("Approve")).toBeNull();
      expect(screen.getByText("Mock runtime: approved stock-in committed to inventory.")).toBeTruthy();
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/confirmations/conf_1/approve"),
        expect.objectContaining({
          method: "POST",
        }),
      );
    });
  });

  it("shows a recoverable error when confirmation rejection fails", async () => {
    rejectShouldFail = true;
    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.getByText("Pending confirmation")).toBeTruthy();
    });

    fireEvent.press(screen.getByText("Reject"));

    await waitFor(() => {
      expect(screen.getByText("Confirmation is not pending")).toBeTruthy();
      expect(screen.getByText("Approve")).toBeTruthy();
      expect(screen.getByText("Reject")).toBeTruthy();
    });
  });

  it("shows a recoverable error when text message submission fails", async () => {
    messagePostShouldFail = true;
    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.getAllByText("restock cola").length).toBeGreaterThan(0);
    });

    fireEvent.changeText(screen.getByPlaceholderText("Type a message"), "   ");
    fireEvent.press(screen.getByText("Send"));

    fireEvent.changeText(screen.getByPlaceholderText("Type a message"), "cola restock");
    fireEvent.press(screen.getByText("Send"));

    await waitFor(() => {
      expect(screen.getByText("Message text is required")).toBeTruthy();
      expect(screen.getAllByText("restock cola").length).toBeGreaterThan(0);
    });
  });

  it("refreshes messages and confirmations when a relevant session-stream event arrives", async () => {
    const { rerender } = render(<ChatScreen />);

    await waitFor(() => {
      expect(messageRequestCount).toBe(1);
      expect(confirmationRequestCount).toBe(1);
    });

    mockLastChatEvent = {
      event_id: "evt_message_created",
      seq: 4,
      event_type: "message.created",
      session_id: "sess_default",
      task_run_id: "task_2",
      message_id: "msg_owner_2",
      occurred_at: "2026-04-05T12:05:00.000Z",
      data: {
        preview_text: "Count chips too",
      },
    };

    rerender(<ChatScreen />);

    await waitFor(() => {
      expect(messageRequestCount).toBe(2);
      expect(confirmationRequestCount).toBe(2);
    });
  });

  it("sends a voice stock-in demo through upload request, completion, and final message post", async () => {
    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.getAllByText("restock cola").length).toBeGreaterThan(0);
    });

    fireEvent.press(screen.getByText("Voice Stock-In Demo"));

    await waitFor(() => {
      expect(mediaUploadRequestCount).toBe(1);
      expect(mediaUploadCompleteCount).toBe(1);
      expect(screen.getAllByText("restock apples today").length).toBeGreaterThan(0);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/sessions/sess_default/messages"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("\"message_type\":\"voice\""),
        }),
      );
    });
  });

  it("shows a recoverable error when voice upload request fails", async () => {
    mediaUploadCreateShouldFail = true;
    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.getAllByText("restock cola").length).toBeGreaterThan(0);
    });

    fireEvent.press(screen.getByText("Voice Query Demo"));

    await waitFor(() => {
      expect(screen.getByText("size_bytes must be greater than 0")).toBeTruthy();
      expect(mediaUploadRequestCount).toBe(1);
      expect(mediaUploadCompleteCount).toBe(0);
    });
  });
});
