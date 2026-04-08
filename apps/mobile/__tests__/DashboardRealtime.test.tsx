import { render, waitFor } from "@testing-library/react-native";

import DashboardScreen from "../src/features/dashboard/screens/DashboardScreen";

const SESSION_TITLE = "Demo Workgroup";

let mockLastDashboardEvent: {
  event_id: string;
  seq: number;
  event_type: string;
  session_id: string;
  task_run_id: string | null;
  message_id: string | null;
  occurred_at: string;
  data: Record<string, unknown>;
} | null = null;
let mockDashboardResetVersion = 0;
const mockNotifyDemoDataReset = jest.fn();


jest.mock("../src/shared/session/useSessionStream", () => ({
  useSessionStream: () => ({
    sessionId: "sess_default",
    sessionTitle: SESSION_TITLE,
    connectionState: "connected",
    bootstrapError: null,
    lastEvent: mockLastDashboardEvent,
    recentEvents: mockLastDashboardEvent === null ? [] : [mockLastDashboardEvent],
    dataResetVersion: mockDashboardResetVersion,
    notifyDemoDataReset: mockNotifyDemoDataReset,
  }),
}));


describe("DashboardScreen realtime refresh", () => {
  let summaryRequests = 0;
  let alertRequests = 0;
  let confirmationRequests = 0;

  beforeEach(() => {
    mockLastDashboardEvent = null;
    mockDashboardResetVersion = 0;
    mockNotifyDemoDataReset.mockReset();
    summaryRequests = 0;
    alertRequests = 0;
    confirmationRequests = 0;

    global.fetch = jest.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
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
            data: [],
            meta: {
              count: 0,
            },
          }),
        });
      }
      if (url.includes("/api/v1/confirmations")) {
        confirmationRequests += 1;
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

  it("refreshes dashboard reads when a relevant session event arrives", async () => {
    const { rerender } = render(<DashboardScreen />);

    await waitFor(() => {
      expect(summaryRequests).toBe(1);
      expect(alertRequests).toBe(1);
      expect(confirmationRequests).toBe(1);
    });

    mockLastDashboardEvent = {
      event_id: "evt_inventory_updated",
      seq: 2,
      event_type: "inventory.updated",
      session_id: "sess_default",
      task_run_id: null,
      message_id: null,
      occurred_at: "2026-04-05T12:01:00.000Z",
      data: {
        item_id: "item_apple",
      },
    };
    rerender(<DashboardScreen />);

    await waitFor(() => {
      expect(summaryRequests).toBe(2);
      expect(alertRequests).toBe(2);
      expect(confirmationRequests).toBe(2);
    });
  });

  it("refreshes dashboard reads when demo reset version changes locally", async () => {
    const { rerender } = render(<DashboardScreen />);

    await waitFor(() => {
      expect(summaryRequests).toBe(1);
      expect(alertRequests).toBe(1);
      expect(confirmationRequests).toBe(1);
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
