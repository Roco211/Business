import { render, screen, waitFor } from "@testing-library/react-native";

import DashboardScreen from "../src/features/dashboard/screens/DashboardScreen";


describe("DashboardScreen", () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/dashboard/summary")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: {
              shop_id: "shop_default",
              today_stock_in_count: 1,
              today_task_completed_count: 1,
              pending_confirmations_count: 1,
              open_low_stock_alert_count: 1,
              last_inventory_event_at: "2026-04-05T12:00:00",
            },
          }),
        });
      }
      if (url.includes("/api/v1/alerts")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: [
              {
                alert_id: "alert_1",
                shop_id: "shop_default",
                alert_type: "low-stock",
                item_id: "item_apple",
                item_name: "Apple",
                status: "open",
                stock: "3.000",
                threshold: "5.000",
                unit: "box",
                created_at: "2026-04-05T12:00:00",
              },
            ],
            meta: {
              count: 1,
            },
          }),
        });
      }
      if (url.includes("/api/v1/confirmations")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: [
              {
                confirmation_id: "confirm_1",
                session_id: "sess_default",
                task_run_id: "task_1",
                confirmation_type: "voice-stock-in",
                status: "pending",
                fields: {
                  summary: "Please confirm the stock-in details before commit.",
                },
                requested_by_employee_id: "xiaoya",
                resolution_payload: null,
                approved_by_actor_id: null,
                created_at: "2026-04-05T12:00:00",
                resolved_at: null,
              },
            ],
            meta: {
              count: 1,
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

  it("renders summary, low-stock alerts, and pending confirmations", async () => {
    render(<DashboardScreen />);

    expect(screen.getByText("Loading dashboard...")).toBeTruthy();

    await waitFor(() => {
      expect(screen.getByText("Dashboard")).toBeTruthy();
      expect(screen.getByText("Today stock-in: 1")).toBeTruthy();
      expect(screen.getByText("Apple")).toBeTruthy();
      expect(screen.getByText("Please confirm the stock-in details before commit.")).toBeTruthy();
    });
  });
});
