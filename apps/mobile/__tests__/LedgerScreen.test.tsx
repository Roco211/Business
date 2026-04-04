import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import LedgerScreen from "../src/features/ledger/screens/LedgerScreen";


describe("LedgerScreen", () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
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
                current_stock: "3.000",
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
                action: "inventory.stock_in_confirmed",
                actor_type: "owner",
                actor_id: "owner_default",
                task_run_id: "task_1",
                target_type: "inventory_item",
                target_id: "item_apple",
                metadata: {
                  item_name: "Apple",
                  quantity_delta: 3,
                  quantity_after: 3,
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
});
