import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import DashboardScreen from "../src/features/dashboard/screens/DashboardScreen";

const SESSION_TITLE = "Demo Workgroup";

let mockDashboardResetVersion = 0;
const mockNotifyDemoDataReset = jest.fn();

jest.mock("../src/shared/session/useSessionStream", () => ({
  useSessionStream: () => ({
    sessionId: "sess_default",
    sessionTitle: SESSION_TITLE,
    connectionState: "connected",
    bootstrapError: null,
    lastEvent: null,
    recentEvents: [],
    dataResetVersion: mockDashboardResetVersion,
    notifyDemoDataReset: mockNotifyDemoDataReset,
  }),
}));

describe("DashboardScreen", () => {
  let summaryRequests = 0;
  let alertRequests = 0;
  let confirmationRequests = 0;

  beforeEach(() => {
    mockDashboardResetVersion = 0;
    mockNotifyDemoDataReset.mockReset();
    summaryRequests = 0;
    alertRequests = 0;
    confirmationRequests = 0;
    global.fetch = jest.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/system/demo/bootstrap")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            data: {
              shop_id: "shop_default",
              session_id: "sess_default",
              inventory_item_count: 3,
              inventory_item_names: ["Coca Cola 500ml", "Cola", "Red Bull 250ml"],
              pending_confirmation_count: 2,
              pending_confirmation_types: ["receipt-stock-in-batch", "stock-out"],
              open_low_stock_alert_count: 1,
              open_low_stock_item_names: ["Cola"],
              message_count: 10,
              task_run_count: 4,
            },
          }),
        });
      }
      if (url.includes("/api/v1/dashboard/summary")) {
        summaryRequests += 1;
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
        alertRequests += 1;
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
        confirmationRequests += 1;
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

  it("renders 今日门店总览 with summary, quick actions, and exception lists", async () => {
    render(<DashboardScreen />);

    expect(screen.getByText("正在同步今日门店总览")).toBeTruthy();

    await waitFor(() => {
      expect(screen.getByText("今日门店总览")).toBeTruthy();
      expect(screen.getByText("聚焦门店库存与待处理事项，先看风险，再安排动作。")).toBeTruthy();
      expect(screen.getByText("今日入库")).toBeTruthy();
      expect(screen.getByText("已完成任务")).toBeTruthy();
      expect(screen.getByText("语音查货")).toBeTruthy();
      expect(screen.getByText("拍照入库")).toBeTruthy();
      expect(screen.getByText("票据识别")).toBeTruthy();
      expect(screen.getAllByText("待确认").length).toBeGreaterThan(0);
      expect(screen.getAllByText("低库存提醒").length).toBeGreaterThan(0);
      expect(screen.getAllByText("待处理确认").length).toBeGreaterThan(0);
      expect(screen.getByText("Apple")).toBeTruthy();
      expect(screen.getByText("Please confirm the stock-in details before commit.")).toBeTruthy();
    });
  });

  it("runs demo reset from dashboard and refreshes dashboard reads", async () => {
    const { rerender } = render(<DashboardScreen />);

    await waitFor(() => {
      expect(screen.getByText("今日门店总览")).toBeTruthy();
      expect(summaryRequests).toBe(1);
      expect(alertRequests).toBe(1);
      expect(confirmationRequests).toBe(1);
    });

    fireEvent.press(screen.getByLabelText("调试工具"));
    fireEvent.press(screen.getByText("重置演示数据"));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/system/demo/bootstrap"),
        expect.objectContaining({
          method: "POST",
        }),
      );
      expect(mockNotifyDemoDataReset).toHaveBeenCalledTimes(1);
    });

    mockDashboardResetVersion = 1;
    rerender(<DashboardScreen />);

    await waitFor(() => {
      expect(summaryRequests).toBe(2);
      expect(alertRequests).toBe(2);
      expect(confirmationRequests).toBe(2);
    });
  });
});
