import { fireEvent, render, screen } from "@testing-library/react-native";

import { ROOT_TABS } from "../../../app/navigation/rootTabConfig";
import DashboardScreen from "./DashboardScreen";

const mockNavigate = jest.fn();
const mockSummaryRefresh = jest.fn();
const mockAlertsRefresh = jest.fn();
const mockPendingRefresh = jest.fn();
const mockNotifyDemoDataReset = jest.fn();
const mockRunDemoBootstrap = jest.fn(async () => null);

let mockShowDeveloperTools = false;

let mockSummaryState: {
  data: {
    shop_id: string;
    today_stock_in_count: number;
    today_task_completed_count: number;
    pending_confirmations_count: number;
    open_low_stock_alert_count: number;
    last_inventory_event_at: string;
  } | null;
  isLoading: boolean;
  error: string | null;
} = {
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
};

let mockAlertsState: { data: Array<Record<string, unknown>>; isLoading: boolean; error: string | null } = {
  data: [],
  isLoading: false,
  error: null,
};

let mockPendingState: { data: Array<Record<string, unknown>>; isLoading: boolean; error: string | null } = {
  data: [],
  isLoading: false,
  error: null,
};

let mockDemoBootstrapState: { isSubmitting: boolean; error: string | null; successMessage: string | null } = {
  isSubmitting: false,
  error: null,
  successMessage: null,
};

let mockSessionStreamState: {
  connectionState: "idle" | "bootstrapping" | "connecting" | "connected" | "disconnected" | "error";
  bootstrapError: string | null;
} = {
  connectionState: "connected",
  bootstrapError: null,
};

jest.mock("../../../shared/dev/isDeveloperToolsEnabled", () => ({
  isDeveloperToolsEnabled: () => mockShowDeveloperTools,
}));

jest.mock("../hooks/useDashboardSummaryQuery", () => ({
  useDashboardSummaryQuery: () => ({
    ...mockSummaryState,
    refresh: mockSummaryRefresh,
  }),
}));

jest.mock("../hooks/useLowStockAlertsQuery", () => ({
  useLowStockAlertsQuery: () => ({
    ...mockAlertsState,
    refresh: mockAlertsRefresh,
  }),
}));

jest.mock("../hooks/usePendingConfirmationsQuery", () => ({
  usePendingConfirmationsQuery: () => ({
    ...mockPendingState,
    refresh: mockPendingRefresh,
  }),
}));

jest.mock("../hooks/useDemoBootstrapMutation", () => ({
  useDemoBootstrapMutation: () => ({
    ...mockDemoBootstrapState,
    runDemoBootstrap: mockRunDemoBootstrap,
  }),
}));

jest.mock("../../../shared/session/useSessionStream", () => ({
  useSessionStream: () => ({
    sessionId: "sess_default",
    sessionTitle: "Demo Workgroup",
    connectionState: mockSessionStreamState.connectionState,
    bootstrapError: mockSessionStreamState.bootstrapError,
    lastEvent: null,
    recentEvents: [],
    dataResetVersion: 0,
    notifyDemoDataReset: mockNotifyDemoDataReset,
  }),
}));

describe("DashboardScreen", () => {
  beforeEach(() => {
    mockShowDeveloperTools = false;
    mockSummaryState = {
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
    };
    mockAlertsState = {
      data: [],
      isLoading: false,
      error: null,
    };
    mockPendingState = {
      data: [],
      isLoading: false,
      error: null,
    };
    mockDemoBootstrapState = {
      isSubmitting: false,
      error: null,
      successMessage: null,
    };
    mockSessionStreamState = {
      connectionState: "connected",
      bootstrapError: null,
    };
    mockNavigate.mockReset();
    mockSummaryRefresh.mockReset();
    mockAlertsRefresh.mockReset();
    mockPendingRefresh.mockReset();
    mockNotifyDemoDataReset.mockReset();
    mockRunDemoBootstrap.mockClear();
  });

  it("shows loading state copy while dashboard data is syncing", () => {
    mockSummaryState = {
      data: null,
      isLoading: true,
      error: null,
    };

    render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

    expect(screen.getByText("正在同步今日门店概览")).toBeTruthy();
    expect(screen.getByText("请稍候，我们正在整理最新库存与待处理事项。")).toBeTruthy();
  });

  it("keeps rendered overview visible during background refresh loading", () => {
    const { rerender } = render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

    expect(screen.getByText("常用操作")).toBeTruthy();
    expect(screen.getByText("语音查货")).toBeTruthy();

    mockSummaryState = {
      ...mockSummaryState,
      isLoading: true,
    };
    mockAlertsState = {
      ...mockAlertsState,
      isLoading: true,
    };
    mockPendingState = {
      ...mockPendingState,
      isLoading: true,
    };

    rerender(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

    expect(screen.getByText("常用操作")).toBeTruthy();
    expect(screen.getByText("语音查货")).toBeTruthy();
    expect(screen.queryByText("正在同步今日门店概览")).toBeNull();
  });

  it("shows a friendly unavailable notice for network errors", () => {
    mockSummaryState = {
      data: null,
      isLoading: false,
      error: "Cannot reach API at http://127.0.0.1:8001 (Network request failed)",
    };

    render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

    expect(screen.getByText("今日总览暂不可用")).toBeTruthy();
    expect(screen.getByText("当前无法连接门店服务，请检查网络后重试。")).toBeTruthy();
  });

  it("keeps dashboard content visible when refresh fails after data has loaded", () => {
    mockSummaryState = {
      ...mockSummaryState,
      error: "Cannot reach API at http://127.0.0.1:8001 (Network request failed)",
    };

    render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

    expect(screen.getByText("常用操作")).toBeTruthy();
    expect(screen.getByText("部分数据刷新失败")).toBeTruthy();
    expect(screen.queryByText("今日总览暂不可用")).toBeNull();
  });

  it("keeps developer tools out of the default dashboard path", () => {
    render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

    expect(screen.getByText("当前健康")).toBeTruthy();
    expect(screen.getByText("连接状态：已连接")).toBeTruthy();
    expect(screen.queryByText("重置演示数据")).toBeNull();
  });

  it("shows developer tools only when the opt-in helper returns true", () => {
    mockShowDeveloperTools = true;

    render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

    expect(screen.getByLabelText("开发调试")).toBeTruthy();
    fireEvent.press(screen.getByLabelText("开发调试"));
    expect(screen.getByText("重置演示数据")).toBeTruthy();
  });

  it("routes every quick action to the workbench with the matching intent", () => {
    render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

    fireEvent.press(screen.getByText("语音查货"));
    fireEvent.press(screen.getByText("拍照入库"));
    fireEvent.press(screen.getByText("票据识别"));
    fireEvent.press(screen.getAllByText("待处理确认")[1]);

    expect(mockNavigate).toHaveBeenNthCalledWith(1, ROOT_TABS.workbench, { initialIntent: "voice-query" });
    expect(mockNavigate).toHaveBeenNthCalledWith(2, ROOT_TABS.workbench, { initialIntent: "photo-stock-in" });
    expect(mockNavigate).toHaveBeenNthCalledWith(3, ROOT_TABS.workbench, { initialIntent: "receipt-entry" });
    expect(mockNavigate).toHaveBeenNthCalledWith(4, ROOT_TABS.workbench, { initialIntent: "pending-confirmations" });
  });
});
