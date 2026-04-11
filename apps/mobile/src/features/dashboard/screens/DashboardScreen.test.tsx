import { fireEvent, render, screen } from "@testing-library/react-native";

import DashboardScreen from "./DashboardScreen";

const mockNotifyDemoDataReset = jest.fn();
const mockRunDemoBootstrap = jest.fn(async () => ({
  shop_id: "shop_default",
  session_id: "sess_default",
  inventory_item_count: 2,
  inventory_item_names: ["Apple", "Cola"],
  pending_confirmation_count: 1,
  pending_confirmation_types: ["voice-stock-in"],
  open_low_stock_alert_count: 1,
  open_low_stock_item_names: ["Apple"],
  message_count: 12,
  task_run_count: 6,
}));
const mockNavigate = jest.fn();
const mockSummaryRefresh = jest.fn();
const mockAlertsRefresh = jest.fn();
const mockPendingRefresh = jest.fn();

let mockShowDeveloperTools = false;
let mockSummaryState = {
  data: {
    shop_id: "shop_default",
    today_stock_in_count: 7,
    today_task_completed_count: 11,
    pending_confirmations_count: 1,
    open_low_stock_alert_count: 1,
    last_inventory_event_at: "2026-04-05T12:00:00",
  },
  isLoading: false,
  error: null as string | null,
};

let mockDemoBootstrapState = {
  isSubmitting: false,
  error: null as string | null,
  successMessage: null as string | null,
};

let mockSessionStreamState = {
  connectionState: "connected" as "idle" | "bootstrapping" | "connecting" | "connected" | "disconnected" | "error",
  bootstrapError: null as string | null,
};

let mockAlertsData = [
  {
    alert_id: "alert_1",
    item_id: "item_apple",
    item_name: "Apple",
    status: "open",
    stock: "3.000",
    threshold: "5.000",
    unit: "box",
  },
];

let mockPendingData = [
  {
    confirmation_id: "confirm_1",
    confirmation_type: "voice-stock-in",
    status: "pending",
    fields: {
      summary: "请确认本次入库明细。",
    },
  },
];

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
    data: mockAlertsData,
    isLoading: false,
    error: null,
    refresh: mockAlertsRefresh,
  }),
}));

jest.mock("../hooks/usePendingConfirmationsQuery", () => ({
  usePendingConfirmationsQuery: () => ({
    data: mockPendingData,
    isLoading: false,
    error: null,
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

describe("DashboardScreen layout", () => {
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
    mockDemoBootstrapState = {
      isSubmitting: false,
      error: null,
      successMessage: null,
    };
    mockSessionStreamState = {
      connectionState: "connected",
      bootstrapError: null,
    };
    mockAlertsData = [
      {
        alert_id: "alert_1",
        item_id: "item_apple",
        item_name: "Apple",
        status: "open",
        stock: "3.000",
        threshold: "5.000",
        unit: "box",
      },
    ];
    mockPendingData = [
      {
        confirmation_id: "confirm_1",
        confirmation_type: "voice-stock-in",
        status: "pending",
        fields: {
          summary: "请确认本次入库明细。",
        },
      },
    ];
    mockNavigate.mockReset();
    mockNotifyDemoDataReset.mockReset();
    mockRunDemoBootstrap.mockClear();
    mockSummaryRefresh.mockReset();
    mockAlertsRefresh.mockReset();
    mockPendingRefresh.mockReset();
  });

  it("shows friendly loading copy while the overview syncs", () => {
    mockSummaryState = {
      data: null,
      isLoading: true,
      error: null,
    };

    render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

    expect(screen.getByText("正在同步今日门店概览")).toBeTruthy();
    expect(screen.getByText("请稍候，我们正在整理最新库存与待处理事项。")).toBeTruthy();
  });

  it("shows a calm unavailable state when dashboard queries fail", () => {
    mockSummaryState = {
      data: null,
      isLoading: false,
      error: "Cannot reach API at http://127.0.0.1:8001 (Network request failed)",
    };

    render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

    expect(screen.getByText("今日总览暂不可用")).toBeTruthy();
    expect(screen.getByText("当前无法连接门店服务，请检查网络后重试。")).toBeTruthy();
  });

  it("shows truthful degraded connection guidance without manual-refresh wording", () => {
    mockSessionStreamState = {
      connectionState: "disconnected",
      bootstrapError: null,
    };

    render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

    expect(screen.getByText("连接状态：连接中断")).toBeTruthy();
    expect(screen.getByText("请检查网络，连接恢复后会自动同步最新数据。")).toBeTruthy();
    expect(screen.queryByText(/手动刷新/i)).toBeNull();
  });

  it("renders the overview-first hero, guidance block, and helper quick actions", () => {
    render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

    expect(screen.getByText("今日门店状态")).toBeTruthy();
    expect(screen.getByText("今天有几项重点要跟进")).toBeTruthy();
    expect(screen.getByText("今天先看店铺概览")).toBeTruthy();
    expect(screen.getByText("店铺概览")).toBeTruthy();
    expect(screen.getByText("推荐下一步")).toBeTruthy();
    expect(screen.getByText("常用操作")).toBeTruthy();
    expect(screen.getByText("一句话查看库存和缺货风险")).toBeTruthy();
  });

  it("shows calm empty states when no low-stock alerts or confirmations exist", () => {
    mockAlertsData = [];
    mockPendingData = [];

    render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

    expect(screen.getByText("库存状态平稳")).toBeTruthy();
    expect(screen.getByText("当前没有低库存预警。")).toBeTruthy();
    expect(screen.getByText("确认队列已清空")).toBeTruthy();
    expect(screen.getByText("暂无待处理确认。")).toBeTruthy();
  });

  it("keeps developer tools out of the default dashboard path", () => {
    render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

    expect(screen.queryByLabelText("调试工具")).toBeNull();
    expect(screen.queryByLabelText("开发调试")).toBeNull();
    expect(screen.queryByText("重置演示数据")).toBeNull();
  });

  it("shows developer tools only when the opt-in helper returns true", () => {
    mockShowDeveloperTools = true;

    render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

    expect(screen.getByLabelText("开发调试")).toBeTruthy();
    fireEvent.press(screen.getByLabelText("开发调试"));
    expect(screen.getByText("重置演示数据")).toBeTruthy();
  });

  it("sends all quick actions to the workbench tab", () => {
    render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

    fireEvent.press(screen.getByText("语音查货"));
    fireEvent.press(screen.getByText("拍照入库"));
    fireEvent.press(screen.getByText("票据识别"));
    fireEvent.press(screen.getAllByText("待处理确认")[1]);

    expect(mockNavigate).toHaveBeenCalledTimes(4);
    expect(mockNavigate).toHaveBeenNthCalledWith(1, "工作台");
    expect(mockNavigate).toHaveBeenNthCalledWith(2, "工作台");
    expect(mockNavigate).toHaveBeenNthCalledWith(3, "工作台");
    expect(mockNavigate).toHaveBeenNthCalledWith(4, "工作台");
  });
});
