import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import LedgerScreen from "../src/features/ledger/screens/LedgerScreen";

const SESSION_TITLE = "Demo Workgroup";

let mockLastLedgerEvent: {
  event_id: string;
  seq: number;
  event_type: string;
  session_id: string;
  task_run_id: string | null;
  message_id: string | null;
  occurred_at: string;
  data: Record<string, unknown>;
} | null = null;
let mockLedgerResetVersion = 0;
const mockNotifyLedgerDemoDataReset = jest.fn();


jest.mock("../src/shared/session/useSessionStream", () => ({
  useSessionStream: () => ({
    sessionId: "sess_default",
    sessionTitle: SESSION_TITLE,
    connectionState: "connected",
    bootstrapError: null,
    lastEvent: mockLastLedgerEvent,
    recentEvents: mockLastLedgerEvent === null ? [] : [mockLastLedgerEvent],
    dataResetVersion: mockLedgerResetVersion,
    notifyDemoDataReset: mockNotifyLedgerDemoDataReset,
  }),
}));


describe("LedgerScreen", () => {
  let inventoryRequests = 0;
  let auditLogRequests = 0;

  beforeEach(() => {
    mockLastLedgerEvent = null;
    mockLedgerResetVersion = 0;
    mockNotifyLedgerDemoDataReset.mockReset();
    inventoryRequests = 0;
    auditLogRequests = 0;
    let correctionApplied = false;
    let stockOutApplied = false;

    global.fetch = jest.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.includes("/api/v1/inventory-events/stock-out") && method === "POST") {
        const payload = JSON.parse(String(init?.body ?? "{}")) as {
          reason?: string;
        };
        if (payload.reason === "Outdated sale") {
          return Promise.resolve({
            ok: false,
            json: async () => ({
              error: {
                code: "inventory_conflict",
                message: "Inventory stock-out conflicts with the current item state",
                details: [],
              },
            }),
          });
        }
        stockOutApplied = true;
        correctionApplied = false;
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: {
              stock_out_event_id: "inv_evt_stock_out_1",
              item_id: "item_apple",
              new_quantity: "1.000",
            },
          }),
        });
      }
      if (url.includes("/api/v1/inventory-events/corrections") && method === "POST") {
        const payload = JSON.parse(String(init?.body ?? "{}")) as {
          expected_quantity?: number;
          reason?: string;
        };
        if (payload.reason === "Outdated snapshot") {
          return Promise.resolve({
            ok: false,
            json: async () => ({
              error: {
                code: "inventory_conflict",
                message: "Inventory correction conflicts with the current item state",
                details: [],
              },
            }),
          });
        }
        correctionApplied = true;
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: {
              correction_event_id: "inv_evt_correction_1",
              item_id: "item_apple",
              new_quantity: "6",
            },
          }),
        });
      }
      if (url.includes("/api/v1/inventory-items?query=ora")) {
        inventoryRequests += 1;
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: [
              {
                item_id: "item_orange",
                shop_id: "shop_default",
                sku: null,
                name: "Orange",
                category: null,
                barcode: null,
                default_unit: "box",
                current_stock: "2.000",
                current_price: "12.50",
                low_stock_threshold: "5.000",
                image_media_id: null,
                is_active: true,
                created_at: "2026-04-05T10:00:00",
                updated_at: "2026-04-05T10:00:00",
              },
            ],
            meta: { count: 1 },
          }),
        });
      }
      if (url.includes("/api/v1/inventory-items")) {
        inventoryRequests += 1;
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: [
              {
                item_id: "item_apple",
                shop_id: "shop_default",
                sku: null,
                name: "Apple",
                category: null,
                barcode: null,
                default_unit: "box",
                current_stock: stockOutApplied ? "1.000" : correctionApplied ? "6.000" : "3.000",
                current_price: "11.50",
                low_stock_threshold: "5.000",
                image_media_id: null,
                is_active: true,
                created_at: "2026-04-05T09:00:00",
                updated_at: "2026-04-05T09:00:00",
              },
            ],
            meta: { count: 1 },
          }),
        });
      }
      if (url.includes("/api/v1/audit-logs")) {
        auditLogRequests += 1;
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: [
              {
                audit_log_id: "audit_1",
                shop_id: "shop_default",
                scope: "inventory",
                action: correctionApplied
                  ? "inventory.correction_submitted"
                  : stockOutApplied
                    ? "inventory.stock_out_submitted"
                    : "inventory.stock_in_confirmed",
                actor_type: "owner",
                actor_id: "owner_default",
                task_run_id: "task_1",
                target_type: "inventory_item",
                target_id: "item_apple",
                metadata: {
                  item_name: "Apple",
                  quantity_delta: correctionApplied ? 4 : stockOutApplied ? -2 : 3,
                  quantity_after: correctionApplied ? 6 : stockOutApplied ? 1 : 3,
                },
                created_at: "2026-04-05T09:00:00",
              },
            ],
            meta: { count: 1 },
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

  it("renders inventory and audit activity, then re-queries inventory on search", async () => {
    render(<LedgerScreen />);

    expect(screen.getByText("Loading ledger...")).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByText("Apple")).toBeTruthy();
      expect(screen.getByText("inventory.stock_in_confirmed")).toBeTruthy();
    });

    fireEvent.changeText(screen.getByPlaceholderText("Search inventory"), "ora");

    await waitFor(() => {
      expect(screen.getByText("Orange")).toBeTruthy();
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/inventory-items?query=ora"),
        expect.any(Object),
      );
    });
  });

  it("submits a correction and refreshes inventory plus audit activity", async () => {
    render(<LedgerScreen />);

    await waitFor(() => {
      expect(screen.getByText("Apple")).toBeTruthy();
      expect(screen.getByText("3.000 box")).toBeTruthy();
    });

    fireEvent.press(screen.getByText("Correct Apple"));
    fireEvent.changeText(screen.getByPlaceholderText("Corrected quantity"), "6");
    fireEvent.changeText(screen.getByPlaceholderText("Correction reason"), "Physical recount");
    fireEvent.press(screen.getByText("Submit correction"));

    await waitFor(() => {
      expect(screen.getByText("6.000 box")).toBeTruthy();
      expect(screen.getByText("inventory.correction_submitted")).toBeTruthy();
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/inventory-events/corrections"),
        expect.objectContaining({
          method: "POST",
        }),
      );
    });
  });

  it("shows a recoverable error when correction submission fails", async () => {
    render(<LedgerScreen />);

    await waitFor(() => {
      expect(screen.getByText("Apple")).toBeTruthy();
    });

    fireEvent.press(screen.getByText("Correct Apple"));
    fireEvent.changeText(screen.getByPlaceholderText("Corrected quantity"), "6");
    fireEvent.changeText(screen.getByPlaceholderText("Correction reason"), "Outdated snapshot");
    fireEvent.press(screen.getByText("Submit correction"));

    await waitFor(() => {
      expect(
        screen.getByText("Inventory correction conflicts with the current item state"),
      ).toBeTruthy();
      expect(screen.getByText("3.000 box")).toBeTruthy();
    });
  });

  it("submits a stock-out and refreshes inventory plus audit activity", async () => {
    render(<LedgerScreen />);

    await waitFor(() => {
      expect(screen.getByText("Apple")).toBeTruthy();
      expect(screen.getByText("3.000 box")).toBeTruthy();
    });

    fireEvent.press(screen.getByText("Stock out Apple"));
    fireEvent.changeText(screen.getByPlaceholderText("Stock-out quantity"), "2");
    fireEvent.changeText(screen.getByPlaceholderText("Stock-out reason"), "Walk-in sale");
    fireEvent.press(screen.getByText("Submit stock-out"));

    await waitFor(() => {
      expect(screen.getByText("1.000 box")).toBeTruthy();
      expect(screen.getByText("inventory.stock_out_submitted")).toBeTruthy();
      expect(screen.getByText("Apple -2")).toBeTruthy();
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/inventory-events/stock-out"),
        expect.objectContaining({
          method: "POST",
        }),
      );
    });
  });

  it("shows a recoverable error when stock-out submission fails", async () => {
    render(<LedgerScreen />);

    await waitFor(() => {
      expect(screen.getByText("Apple")).toBeTruthy();
    });

    fireEvent.press(screen.getByText("Stock out Apple"));
    fireEvent.changeText(screen.getByPlaceholderText("Stock-out quantity"), "2");
    fireEvent.changeText(screen.getByPlaceholderText("Stock-out reason"), "Outdated sale");
    fireEvent.press(screen.getByText("Submit stock-out"));

    await waitFor(() => {
      expect(
        screen.getByText("Inventory stock-out conflicts with the current item state"),
      ).toBeTruthy();
      expect(screen.getByText("3.000 box")).toBeTruthy();
    });
  });

  it("refreshes inventory and audit reads when a relevant session event arrives", async () => {
    const { rerender } = render(<LedgerScreen />);

    await waitFor(() => {
      expect(inventoryRequests).toBe(1);
      expect(auditLogRequests).toBe(1);
    });

    mockLastLedgerEvent = {
      event_id: "evt_inventory_updated",
      seq: 2,
      event_type: "inventory.updated",
      session_id: "sess_default",
      task_run_id: null,
      message_id: null,
      occurred_at: "2026-04-05T12:05:00.000Z",
      data: {
        item_id: "item_apple",
      },
    };
    rerender(<LedgerScreen />);

    await waitFor(() => {
      expect(inventoryRequests).toBe(2);
      expect(auditLogRequests).toBe(2);
    });
  });

  it("refreshes inventory and audit reads when demo reset version changes locally", async () => {
    const { rerender } = render(<LedgerScreen />);

    await waitFor(() => {
      expect(inventoryRequests).toBe(1);
      expect(auditLogRequests).toBe(1);
    });

    mockLedgerResetVersion = 1;
    rerender(<LedgerScreen />);

    await waitFor(() => {
      expect(inventoryRequests).toBe(2);
      expect(auditLogRequests).toBe(2);
    });
  });
});
