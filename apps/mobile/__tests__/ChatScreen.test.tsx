import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import ChatScreen from "../src/features/chat/screens/ChatScreen";

const SESSION_TITLE = "\u6570\u5b57\u5458\u5de5\u5de5\u4f5c\u7fa4";

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
let includeReceiptConfirmation = false;
let receiptConfirmationResolved = false;
let messageRequestCount = 0;
let confirmationRequestCount = 0;
let mediaUploadRequestCount = 0;
let mediaUploadCompleteCount = 0;

jest.mock("../src/shared/session/useSessionStream", () => ({
  useSessionStream: () => ({
    sessionId: "sess_default",
    sessionTitle: SESSION_TITLE,
    connectionState: "connected",
    bootstrapError: null,
    lastEvent: mockLastChatEvent,
    recentEvents: mockLastChatEvent === null ? [] : [mockLastChatEvent],
  }),
}));

describe("ChatScreen", () => {
  async function waitForChatReady() {
    await waitFor(
      () => {
        expect(screen.getByText(SESSION_TITLE)).toBeTruthy();
        expect(screen.getByText("connected")).toBeTruthy();
        expect(screen.getAllByText("restock cola").length).toBeGreaterThan(0);
      },
      { timeout: 3000 },
    );
  }

  beforeEach(() => {
    mockLastChatEvent = null;
    approvalShouldFail = false;
    rejectShouldFail = false;
    messagePostShouldFail = false;
    mediaUploadCreateShouldFail = false;
    mediaUploadCompleteShouldFail = false;
    includeReceiptConfirmation = false;
    receiptConfirmationResolved = false;
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

    function ensureReceiptFixture() {
      if (!includeReceiptConfirmation || receiptConfirmationResolved) {
        return;
      }
      const hasReceiptMessages = messages.some((message) => message.task_run_id === "task_receipt_confirm_1");
      if (!hasReceiptMessages) {
        messages.push(
          {
            message_id: "msg_receipt_owner_1",
            session_id: "sess_default",
            actor_type: "owner",
            actor_id: "owner_default",
            message_type: "receipt-image",
            text: "receipt scan today",
            media_ids: ["receipt_demo"],
            task_run_id: "task_receipt_confirm_1",
            created_at: "2026-04-05T12:10:00.000Z",
          },
          {
            message_id: "msg_receipt_system_1",
            session_id: "sess_default",
            actor_type: "system",
            actor_id: "runtime",
            message_type: "text",
            text: "Mock runtime: please confirm the receipt line items before committing inventory.",
            media_ids: [],
            task_run_id: "task_receipt_confirm_1",
            created_at: "2026-04-05T12:10:03.000Z",
          },
        );
      }
      const hasReceiptConfirmation = pendingConfirmations.some(
        (confirmation) => confirmation.confirmation_id === "conf_receipt_1",
      );
      if (!hasReceiptConfirmation) {
        pendingConfirmations.push({
          confirmation_id: "conf_receipt_1",
          session_id: "sess_default",
          task_run_id: "task_receipt_confirm_1",
          confirmation_type: "receipt-stock-in-batch",
          status: "pending",
          fields: {
            summary: "Please confirm the receipt line items before committing inventory.",
            ocr_document_id: "ocr_1",
            total_amount: 147,
            low_confidence_fields: [],
            draft_items: [
              {
                line_id: "line_1",
                item_id: null,
                item_name: "Red Bull 250ml",
                quantity: 3,
                unit: "can",
                price: 41,
              },
              {
                line_id: "line_2",
                item_id: null,
                item_name: "Coca Cola 500ml",
                quantity: 2,
                unit: "bottle",
                price: 12,
              },
            ],
            required_item_fields: ["item_name", "quantity", "unit", "price"],
          },
          requested_by_employee_id: "emp_mock",
          resolution_payload: null,
          approved_by_actor_id: null,
          created_at: "2026-04-05T12:10:04.000Z",
          resolved_at: null,
        });
      }
    }

    global.fetch = jest.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      ensureReceiptFixture();

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
        const payload = JSON.parse(String(init?.body ?? "{}")) as {
          media_type?: string;
        };
        const mediaId =
          payload.media_type === "image"
            ? "image_query_demo"
            : payload.media_type === "receipt-image"
              ? "receipt_demo"
              : "media_voice_demo_1";
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: {
              media_id: mediaId,
              upload_url: `https://mock.example/uploads/${mediaId}`,
              public_url: `https://mock.example/media/${mediaId}`,
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

      if (url.includes("/api/v1/confirmations/conf_receipt_1/approve") && method === "POST") {
        if (approvalShouldFail) {
          return Promise.resolve({
            ok: false,
            json: async () => ({
              error: {
                code: "confirmation_fields_invalid",
                message: "items must be a non-empty list",
                details: [],
              },
            }),
          });
        }
        const receiptIndex = pendingConfirmations.findIndex(
          (confirmation) => confirmation.confirmation_id === "conf_receipt_1",
        );
        if (receiptIndex >= 0) {
          pendingConfirmations.splice(receiptIndex, 1);
        }
        receiptConfirmationResolved = true;
        messages.push({
          message_id: "msg_receipt_system_approved",
          session_id: "sess_default",
          actor_type: "system",
          actor_id: "runtime",
          message_type: "text",
          text: "Mock runtime: receipt stock-in committed for 2 line items.",
          media_ids: [],
          task_run_id: "task_receipt_confirm_1",
          created_at: "2026-04-05T12:10:06.000Z",
        });
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: {
              confirmation_id: "conf_receipt_1",
              session_id: "sess_default",
              task_run_id: "task_receipt_confirm_1",
              confirmation_type: "receipt-stock-in-batch",
              status: "approved",
              fields: {
                summary: "Please confirm the receipt line items before committing inventory.",
              },
              requested_by_employee_id: "emp_mock",
              resolution_payload: JSON.parse(String(init?.body ?? "{\"fields\":{}}")).fields,
              approved_by_actor_id: "owner_default",
              created_at: "2026-04-05T12:10:04.000Z",
              resolved_at: "2026-04-05T12:10:06.000Z",
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
        const isVoice = payload.message_type === "voice";
        const isImage = payload.message_type === "image";
        const isReceipt = payload.message_type === "receipt-image";
        messages.push({
          message_id: isVoice ? "msg_voice_demo_1" : isImage ? "msg_image_demo_1" : isReceipt ? "msg_receipt_demo_1" : "msg_owner_2",
          session_id: "sess_default",
          actor_type: "owner",
          actor_id: "owner_default",
          message_type: payload.message_type ?? "text",
          text: payload.text ?? "",
          media_ids: payload.media_ids ?? [],
          task_run_id: isVoice ? "task_voice_1" : isImage ? "task_image_1" : isReceipt ? "task_receipt_1" : "task_2",
          created_at: "2026-04-05T12:05:00.000Z",
        });
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: {
              message_id: isVoice ? "msg_voice_demo_1" : isImage ? "msg_image_demo_1" : isReceipt ? "msg_receipt_demo_1" : "msg_owner_2",
              task_run_id: isVoice ? "task_voice_1" : isImage ? "task_image_1" : isReceipt ? "task_receipt_1" : "task_2",
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

    await waitForChatReady();
    expect(
      screen.getByText("Mock runtime: please confirm the stock-in details before commit."),
    ).toBeTruthy();
  });

  it("submits a text message and refreshes the timeline", async () => {
    render(<ChatScreen />);

    await waitForChatReady();

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

  it("renders a pending receipt confirmation card and approves edited line items from chat", async () => {
    includeReceiptConfirmation = true;
    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.getByText("Receipt confirmation")).toBeTruthy();
      expect(screen.getByDisplayValue("Red Bull 250ml")).toBeTruthy();
      expect(screen.getByDisplayValue("Coca Cola 500ml")).toBeTruthy();
    });

    fireEvent.changeText(screen.getByPlaceholderText("Quantity 1"), "4");
    fireEvent.changeText(screen.getByPlaceholderText("Price 2"), "13");
    fireEvent.press(screen.getByText("Approve Receipt"));

    await waitFor(() => {
      expect(screen.queryByText("Approve Receipt")).toBeNull();
      expect(screen.getByText("Mock runtime: receipt stock-in committed for 2 line items.")).toBeTruthy();
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/confirmations/conf_receipt_1/approve"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("\"line_id\":\"line_1\""),
        }),
      );
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/confirmations/conf_receipt_1/approve"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("\"quantity\":4"),
        }),
      );
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/confirmations/conf_receipt_1/approve"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("\"price\":13"),
        }),
      );
    });
  });

  it("shows a recoverable error when text message submission fails", async () => {
    messagePostShouldFail = true;
    render(<ChatScreen />);

    await waitForChatReady();

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

    await waitForChatReady();

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

    await waitForChatReady();

    fireEvent.press(screen.getByText("Voice Query Demo"));

    await waitFor(() => {
      expect(screen.getByText("size_bytes must be greater than 0")).toBeTruthy();
      expect(mediaUploadRequestCount).toBe(1);
      expect(mediaUploadCompleteCount).toBe(0);
    });
  });

  it("sends a photo query demo through upload request, completion, and final message post", async () => {
    render(<ChatScreen />);

    await waitForChatReady();

    fireEvent.press(screen.getByText("Photo Query Demo"));

    await waitFor(() => {
      expect(mediaUploadRequestCount).toBe(1);
      expect(mediaUploadCompleteCount).toBe(1);
      expect(screen.getAllByText("check shelf stock for red bull").length).toBeGreaterThan(0);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/sessions/sess_default/messages"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("\"message_type\":\"image\""),
        }),
      );
    });
  });

  it("sends a receipt OCR demo through upload request, completion, and final message post", async () => {
    render(<ChatScreen />);

    await waitForChatReady();

    fireEvent.press(screen.getByText("Receipt OCR Demo"));

    await waitFor(() => {
      expect(mediaUploadRequestCount).toBe(1);
      expect(mediaUploadCompleteCount).toBe(1);
      expect(screen.getAllByText("receipt scan today").length).toBeGreaterThan(0);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/sessions/sess_default/messages"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("\"message_type\":\"receipt-image\""),
        }),
      );
    });
  });

  it("shows a recoverable error when photo upload request fails", async () => {
    mediaUploadCreateShouldFail = true;
    render(<ChatScreen />);

    await waitForChatReady();

    fireEvent.press(screen.getByText("Photo Query Demo"));

    await waitFor(() => {
      expect(screen.getByText("size_bytes must be greater than 0")).toBeTruthy();
      expect(mediaUploadRequestCount).toBe(1);
      expect(mediaUploadCompleteCount).toBe(0);
    });
  });
});
