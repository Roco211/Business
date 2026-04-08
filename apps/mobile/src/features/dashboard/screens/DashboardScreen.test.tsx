import { fireEvent, render, screen } from "@testing-library/react-native";

import { ROOT_TABS } from "../../../app/navigation/rootTabConfig";
import DashboardScreen from "./DashboardScreen";

const mockNavigate = jest.fn();

jest.mock("../hooks/useDashboardSummaryQuery", () => ({
  useDashboardSummaryQuery: () => ({
    data: {
      shop_id: "shop_default",
      today_stock_in_count: 7,
      today_task_completed_count: 11,
      pending_confirmations_count: 1,
      open_low_stock_alert_count: 1,
      last_inventory_event_at: "2026-04-05T12:00:00",
    },
    isLoading: false,
    error: null,
    refresh: jest.fn(),
  }),
}));

jest.mock("../hooks/useLowStockAlertsQuery", () => ({
  useLowStockAlertsQuery: () => ({
    data: [],
    isLoading: false,
    error: null,
    refresh: jest.fn(),
  }),
}));

jest.mock("../hooks/usePendingConfirmationsQuery", () => ({
  usePendingConfirmationsQuery: () => ({
    data: [],
    isLoading: false,
    error: null,
    refresh: jest.fn(),
  }),
}));

jest.mock("../hooks/useDemoBootstrapMutation", () => ({
  useDemoBootstrapMutation: () => ({
    isSubmitting: false,
    error: null,
    successMessage: null,
    runDemoBootstrap: jest.fn(),
  }),
}));

jest.mock("../../../shared/session/useSessionStream", () => ({
  useSessionStream: () => ({
    sessionId: "sess_default",
    sessionTitle: "Demo Workgroup",
    connectionState: "connected",
    bootstrapError: null,
    lastEvent: null,
    recentEvents: [],
    dataResetVersion: 0,
    notifyDemoDataReset: jest.fn(),
  }),
}));

describe("DashboardScreen", () => {
  beforeEach(() => {
    mockNavigate.mockReset();
  });

  it("routes every quick action to the workbench with the matching intent", () => {
    render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

    fireEvent.press(screen.getByText("语音查货"));
    fireEvent.press(screen.getByText("拍照入库"));
    fireEvent.press(screen.getByText("票据识别"));
    fireEvent.press(screen.getByText("待确认"));

    expect(mockNavigate).toHaveBeenNthCalledWith(1, ROOT_TABS.workbench, { initialIntent: "voice-query" });
    expect(mockNavigate).toHaveBeenNthCalledWith(2, ROOT_TABS.workbench, { initialIntent: "photo-stock-in" });
    expect(mockNavigate).toHaveBeenNthCalledWith(3, ROOT_TABS.workbench, { initialIntent: "receipt-entry" });
    expect(mockNavigate).toHaveBeenNthCalledWith(4, ROOT_TABS.workbench, { initialIntent: "pending-confirmations" });
  });
});
