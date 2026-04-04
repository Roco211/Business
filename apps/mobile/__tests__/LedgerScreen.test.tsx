import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import LedgerScreen from "../src/features/ledger/screens/LedgerScreen";


describe("LedgerScreen", () => {
  beforeEach(() => {
    let correctionApplied = false;

    global.fetch = jest.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
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
                current_stock: correctionApplied ? "6.000" : "3.000",
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
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: [
              {
                audit_log_id: "audit_1",
                shop_id: "shop_default",
                scope: "inventory",
                action: correctionApplied ? "inventory.correction_submitted" : "inventory.stock_in_confirmed",
                actor_type: "owner",
                actor_id: "owner_default",
                task_run_id: "task_1",
                target_type: "inventory_item",
                target_id: "item_apple",
                metadata: {
                  item_name: "Apple",
                  quantity_delta: correctionApplied ? 4 : 3,
                  quantity_after: correctionApplied ? 6 : 3,
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
});
