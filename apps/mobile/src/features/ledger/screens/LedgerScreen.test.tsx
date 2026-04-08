import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import LedgerScreen from "./LedgerScreen";
import { useAuditLogsQuery } from "../hooks/useAuditLogsQuery";
import { useCreateCorrectionMutation } from "../hooks/useCreateCorrectionMutation";
import { useCreateStockOutMutation } from "../hooks/useCreateStockOutMutation";
import { useInventoryItemsQuery } from "../hooks/useInventoryItemsQuery";
import { useSessionStream } from "../../../shared/session/useSessionStream";

jest.mock("../hooks/useInventoryItemsQuery");
jest.mock("../hooks/useAuditLogsQuery");
jest.mock("../hooks/useCreateCorrectionMutation");
jest.mock("../hooks/useCreateStockOutMutation");
jest.mock("../../../shared/session/useSessionStream");

const mockedUseInventoryItemsQuery = useInventoryItemsQuery as jest.MockedFunction<
  typeof useInventoryItemsQuery
>;
const mockedUseAuditLogsQuery = useAuditLogsQuery as jest.MockedFunction<typeof useAuditLogsQuery>;
const mockedUseCreateCorrectionMutation = useCreateCorrectionMutation as jest.MockedFunction<
  typeof useCreateCorrectionMutation
>;
const mockedUseCreateStockOutMutation = useCreateStockOutMutation as jest.MockedFunction<
  typeof useCreateStockOutMutation
>;
const mockedUseSessionStream = useSessionStream as jest.MockedFunction<typeof useSessionStream>;

describe("LedgerScreen workspace", () => {
  const inventoryRefresh = jest.fn();
  const auditRefresh = jest.fn();
  const submitCorrection = jest.fn();
  const submitStockOut = jest.fn();

  beforeEach(() => {
    inventoryRefresh.mockReset();
    auditRefresh.mockReset();
    submitCorrection.mockReset();
    submitStockOut.mockReset();
    submitCorrection.mockResolvedValue({ data: { correction_event_id: "evt_1" } });
    submitStockOut.mockResolvedValue({ data: { stock_out_event_id: "evt_2" } });

    mockedUseInventoryItemsQuery.mockReturnValue({
      data: [
        {
          item_id: "item_apple",
          name: "Apple",
          default_unit: "box",
          current_stock: "3.000",
          current_price: "11.50",
        },
      ],
      isLoading: false,
      error: null,
      refresh: inventoryRefresh,
    });
    mockedUseAuditLogsQuery.mockReturnValue({
      data: [
        {
          audit_log_id: "audit_1",
          action: "inventory.stock_in_confirmed",
          created_at: "2026-04-05T09:00:00",
          metadata: {
            item_name: "Apple",
            quantity_delta: 3,
          },
        },
      ],
      isLoading: false,
      error: null,
      refresh: auditRefresh,
    });
    mockedUseCreateCorrectionMutation.mockReturnValue({
      isSubmitting: false,
      error: null,
      submitCorrection,
    });
    mockedUseCreateStockOutMutation.mockReturnValue({
      isSubmitting: false,
      error: null,
      submitStockOut,
    });
    mockedUseSessionStream.mockReturnValue({
      sessionId: "sess_default",
      sessionTitle: "Demo Workgroup",
      connectionState: "connected",
      bootstrapError: null,
      lastEvent: null,
      recentEvents: [],
      dataResetVersion: 0,
      notifyDemoDataReset: jest.fn(),
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it("renders readable Chinese copy for search, action panel, and activity timeline", async () => {
    render(<LedgerScreen />);

    await waitFor(() => {
      expect(screen.getByText("库存台账")).toBeTruthy();
      expect(screen.getByText("搜索与筛选")).toBeTruthy();
      expect(screen.getByText("操作面板")).toBeTruthy();
      expect(screen.getByText("活动时间线")).toBeTruthy();
      expect(screen.getByLabelText("搜索库存")).toBeTruthy();
      expect(screen.getByTestId("inventory-card-item_apple")).toBeTruthy();
      expect(screen.getByTestId("audit-timeline-item-audit_1")).toBeTruthy();
    });
  });

  it("shows calm loading state", () => {
    mockedUseInventoryItemsQuery.mockReturnValue({
      data: [],
      isLoading: true,
      error: null,
      refresh: inventoryRefresh,
    });
    mockedUseAuditLogsQuery.mockReturnValue({
      data: [],
      isLoading: true,
      error: null,
      refresh: auditRefresh,
    });

    render(<LedgerScreen />);

    expect(screen.getByTestId("ledger-loading-state")).toBeTruthy();
    expect(screen.getByText("正在同步库存台账")).toBeTruthy();
    expect(screen.getByText("请稍候，我们正在整理库存与最近活动。")).toBeTruthy();
    expect(screen.queryByText("Loading ledger...")).toBeNull();
  });

  it("shows a unified unavailable state when ledger data cannot load", () => {
    mockedUseInventoryItemsQuery.mockReturnValue({
      data: [],
      isLoading: false,
      error: "Cannot reach API at http://127.0.0.1:8001 (Network request failed)",
      refresh: inventoryRefresh,
    });
    mockedUseAuditLogsQuery.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
      refresh: auditRefresh,
    });

    render(<LedgerScreen />);

    expect(screen.getByTestId("ledger-error-state")).toBeTruthy();
    expect(screen.getByText("库存台账暂时不可用")).toBeTruthy();
    expect(screen.getByText("当前无法连接门店服务，请检查网络后重试。")).toBeTruthy();
  });

  it("shows clearer empty copy when search has no matches", async () => {
    mockedUseInventoryItemsQuery.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
      refresh: inventoryRefresh,
    });

    render(<LedgerScreen />);

    await waitFor(() => {
      expect(screen.getByText("暂未找到匹配商品")).toBeTruthy();
      expect(screen.getByText("试试更换关键词，或稍后再刷新库存数据。")).toBeTruthy();
    });
  });

  it("submits correction through the action panel and refreshes data", async () => {
    render(<LedgerScreen />);

    fireEvent.press(screen.getByTestId("inventory-card-item_apple-action-correction"));
    fireEvent.changeText(screen.getByTestId("ledger-correction-quantity-input"), "5");
    fireEvent.changeText(screen.getByTestId("ledger-correction-reason-input"), "Manual recount");
    fireEvent.press(screen.getByTestId("ledger-action-submit-button"));

    await waitFor(() => {
      expect(submitCorrection).toHaveBeenCalledWith({
        item_id: "item_apple",
        expected_quantity: 3,
        corrected_quantity: 5,
        reason: "Manual recount",
      });
      expect(inventoryRefresh).toHaveBeenCalled();
      expect(auditRefresh).toHaveBeenCalled();
    });
  });

  it("does not leak correction draft when switching item then switching action in panel", async () => {
    mockedUseInventoryItemsQuery.mockReturnValue({
      data: [
        {
          item_id: "item_apple",
          name: "Apple",
          default_unit: "box",
          current_stock: "3.000",
          current_price: "11.50",
        },
        {
          item_id: "item_orange",
          name: "Orange",
          default_unit: "box",
          current_stock: "9.000",
          current_price: "12.50",
        },
      ],
      isLoading: false,
      error: null,
      refresh: inventoryRefresh,
    });

    render(<LedgerScreen />);

    fireEvent.press(screen.getByTestId("inventory-card-item_apple-action-correction"));
    fireEvent.changeText(screen.getByTestId("ledger-correction-quantity-input"), "7");
    fireEvent.changeText(screen.getByTestId("ledger-correction-reason-input"), "Apple draft");

    fireEvent.press(screen.getByTestId("inventory-card-item_orange-action-stock-out"));

    const correctionSwitchButtons = screen.getAllByRole("button", { name: "库存修正" });
    fireEvent.press(correctionSwitchButtons[correctionSwitchButtons.length - 1]);
    fireEvent.changeText(screen.getByTestId("ledger-correction-reason-input"), "Orange correction");
    fireEvent.press(screen.getByTestId("ledger-action-submit-button"));

    await waitFor(() => {
      expect(submitCorrection).toHaveBeenCalledWith({
        item_id: "item_orange",
        expected_quantity: 9,
        corrected_quantity: 9,
        reason: "Orange correction",
      });
    });
  });
});
