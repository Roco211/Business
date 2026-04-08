import { act, fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import { ROOT_TABS } from "../../../app/navigation/rootTabConfig";
import { FRONTLINE_STATUS_COPY } from "../../../shared/copy/frontlineStatus";
import { useSessionStream } from "../../../shared/session/useSessionStream";
import ChatScreen from "./ChatScreen";
import { useChatPendingConfirmationsQuery } from "../hooks/useChatPendingConfirmationsQuery";
import { useSendMessageMutation } from "../hooks/useSendMessageMutation";
import { useSessionMessagesQuery } from "../hooks/useSessionMessagesQuery";

jest.mock("../../../shared/session/useSessionStream");
jest.mock("../hooks/useSessionMessagesQuery");
jest.mock("../hooks/useChatPendingConfirmationsQuery");
jest.mock("../hooks/useSendMessageMutation");

const mockedUseSessionStream = useSessionStream as jest.MockedFunction<typeof useSessionStream>;
const mockedUseSessionMessagesQuery = useSessionMessagesQuery as jest.MockedFunction<
  typeof useSessionMessagesQuery
>;
const mockedUseChatPendingConfirmationsQuery = useChatPendingConfirmationsQuery as jest.MockedFunction<
  typeof useChatPendingConfirmationsQuery
>;
const mockedUseSendMessageMutation = useSendMessageMutation as jest.MockedFunction<
  typeof useSendMessageMutation
>;

describe("ChatScreen (workbench shell)", () => {
  beforeEach(() => {
    mockedUseSessionStream.mockReturnValue({
      sessionId: "sess_1",
      sessionTitle: "Store shift session",
      connectionState: "connected",
      bootstrapError: null,
      retryBootstrap: jest.fn(),
      lastEvent: null,
      recentEvents: [],
      dataResetVersion: 0,
      notifyDemoDataReset: jest.fn(),
    });
    mockedUseSessionMessagesQuery.mockReturnValue({
      data: [
        {
          message_id: "msg_1",
          session_id: "sess_1",
          actor_type: "owner",
          actor_id: "owner_1",
          message_type: "text",
          text: "count beverage stock",
          media_ids: [],
          task_run_id: "task_1",
          created_at: "2026-04-05T12:00:00.000Z",
        },
      ],
      isLoading: false,
      error: null,
      refresh: jest.fn(),
    });
    mockedUseChatPendingConfirmationsQuery.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
      refresh: jest.fn(),
    });
    mockedUseSendMessageMutation.mockReturnValue({
      isSubmitting: false,
      error: null,
      submitMessage: jest.fn().mockResolvedValue({
        data: { message_id: "msg_2", task_run_id: "task_2", status: "created" },
      }),
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it("renders business-language guided entry actions on the default path", async () => {
    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.getByText("聊天工作台")).toBeTruthy();
      expect(screen.getByText("Store shift session")).toBeTruthy();
      expect(screen.getByText("连接状态")).toBeTruthy();
      expect(screen.getByText("已连接")).toBeTruthy();
      expect(screen.getByText("业务快捷入口")).toBeTruthy();
      expect(screen.getByText("语音盘点")).toBeTruthy();
      expect(screen.getByText("拍照入库")).toBeTruthy();
      expect(screen.getByText("票据录入")).toBeTruthy();
      expect(screen.queryByText("调试: 语音查询 (旧演示)")).toBeNull();
      expect(screen.getByText("店主")).toBeTruthy();
      expect(screen.getByText("类型：文本")).toBeTruthy();
      expect(screen.getByPlaceholderText("描述你的请求")).toBeTruthy();
      expect(screen.getByText("发送消息")).toBeTruthy();
      expect(screen.getByText("调试工具")).toBeTruthy();
      expect(screen.getByText("展开调试信息")).toBeTruthy();
    });
  });

  it("shows unified loading copy before the first message batch arrives", () => {
    mockedUseSessionMessagesQuery.mockReturnValue({
      data: [],
      isLoading: true,
      error: null,
      refresh: jest.fn(),
    });

    render(<ChatScreen />);

    expect(screen.getByText("正在同步工作台")).toBeTruthy();
    expect(screen.getByText("请稍候，我们正在整理会话消息与待确认事项。")).toBeTruthy();
  });

  it("keeps the screen in preparing mode while bootstrap is in progress and session is still null", () => {
    mockedUseSessionStream.mockReturnValue({
      sessionId: null,
      sessionTitle: null,
      connectionState: "bootstrapping",
      bootstrapError: null,
      retryBootstrap: jest.fn(),
      lastEvent: null,
      recentEvents: [],
      dataResetVersion: 0,
      notifyDemoDataReset: jest.fn(),
    });
    mockedUseSessionMessagesQuery.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
      refresh: jest.fn(),
    });

    render(<ChatScreen />);

    expect(screen.getByTestId("chat-bootstrap-loading")).toBeTruthy();
    expect(screen.queryByTestId("chat-workbench-header")).toBeNull();
    expect(screen.queryByTestId("chat-send-button")).toBeNull();
  });

  it("disables composer send when there is no session and bootstrap is not preparing", () => {
    const submitMessage = jest.fn();
    mockedUseSessionStream.mockReturnValue({
      sessionId: null,
      sessionTitle: null,
      connectionState: "idle",
      bootstrapError: null,
      retryBootstrap: jest.fn(),
      lastEvent: null,
      recentEvents: [],
      dataResetVersion: 0,
      notifyDemoDataReset: jest.fn(),
    });
    mockedUseSessionMessagesQuery.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
      refresh: jest.fn(),
    });
    mockedUseSendMessageMutation.mockReturnValue({
      isSubmitting: false,
      error: null,
      submitMessage,
    });

    render(<ChatScreen />);

    const sendButton = screen.getByTestId("chat-send-button");
    expect(sendButton.props.accessibilityState?.disabled).toBe(true);

    fireEvent.press(sendButton);
    expect(submitMessage).not.toHaveBeenCalled();
  });

  it("hides legacy media demos until debug disclosure is opened", async () => {
    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.queryByText("调试: 语音查询 (旧演示)")).toBeNull();
    });

    fireEvent.press(screen.getByLabelText("调试工具"));

    await waitFor(() => {
      expect(screen.getByText("调试: 语音查询 (旧演示)")).toBeTruthy();
      expect(screen.getByText("收起调试信息")).toBeTruthy();
    });
  });

  it("presents runtime text without leaking mock runtime copy", async () => {
    mockedUseSessionMessagesQuery.mockReturnValue({
      data: [
        {
          message_id: "msg_2",
          session_id: "sess_1",
          actor_type: "system",
          actor_id: "runtime",
          message_type: "text",
          text: "Mock runtime: stock query accepted and queued for simulation.",
          media_ids: [],
          task_run_id: "task_2",
          created_at: "2026-04-05T12:01:00.000Z",
        },
      ],
      isLoading: false,
      error: null,
      refresh: jest.fn(),
    });

    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.getByText(FRONTLINE_STATUS_COPY.realtimeDegraded)).toBeTruthy();
      expect(screen.queryByText("Mock runtime: stock query accepted and queued for simulation.")).toBeNull();
    });
  });

  it("does not rewrite owner-authored text that starts with mock runtime prefix", async () => {
    mockedUseSessionMessagesQuery.mockReturnValue({
      data: [
        {
          message_id: "msg_2",
          session_id: "sess_1",
          actor_type: "owner",
          actor_id: "owner_1",
          message_type: "text",
          text: "Mock runtime: stock query accepted and queued for simulation.",
          media_ids: [],
          task_run_id: "task_2",
          created_at: "2026-04-05T12:01:00.000Z",
        },
      ],
      isLoading: false,
      error: null,
      refresh: jest.fn(),
    });

    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.getByText("Mock runtime: stock query accepted and queued for simulation.")).toBeTruthy();
      expect(screen.queryByText(FRONTLINE_STATUS_COPY.realtimeDegraded)).toBeNull();
    });
  });

  it("shows fallback copy when runtime payload only contains mock runtime prefix", async () => {
    mockedUseSessionMessagesQuery.mockReturnValue({
      data: [
        {
          message_id: "msg_2",
          session_id: "sess_1",
          actor_type: "system",
          actor_id: "runtime",
          message_type: "text",
          text: "Mock runtime:      ",
          media_ids: [],
          task_run_id: "task_2",
          created_at: "2026-04-05T12:01:00.000Z",
        },
      ],
      isLoading: false,
      error: null,
      refresh: jest.fn(),
    });

    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.getByText("此消息暂无可显示内容")).toBeTruthy();
      expect(screen.queryByText("Mock runtime:")).toBeNull();
    });
  });

  it("renders chinese fallback copy for non-text messages without visible text", async () => {
    mockedUseSessionMessagesQuery.mockReturnValue({
      data: [
        {
          message_id: "msg_2",
          session_id: "sess_1",
          actor_type: "system",
          actor_id: "runtime",
          message_type: "image",
          text: "   ",
          media_ids: ["media_1"],
          task_run_id: "task_2",
          created_at: "2026-04-05T12:01:00.000Z",
        },
      ],
      isLoading: false,
      error: null,
      refresh: jest.fn(),
    });

    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.getByText("系统")).toBeTruthy();
      expect(screen.getByText("类型：图片")).toBeTruthy();
      expect(screen.getByText("此消息暂无可显示内容")).toBeTruthy();
    });
  });

  it("shows calm empty-state copy when the session has no messages yet", async () => {
    mockedUseSessionMessagesQuery.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
      refresh: jest.fn(),
    });

    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.getByText("工作台里还没有新消息")).toBeTruthy();
      expect(screen.getByText("可以先用引导入口，也可以直接发送文字请求。")).toBeTruthy();
    });
  });

  it("shows bootstrap-specific recovery copy when session bootstrap fails", async () => {
    mockedUseSessionStream.mockReturnValue({
      sessionId: "sess_1",
      sessionTitle: "Store shift session",
      connectionState: "error",
      bootstrapError: "Cannot reach API at http://192.168.1.4:8001 (Network request failed)",
      retryBootstrap: jest.fn(),
      lastEvent: null,
      recentEvents: [],
      dataResetVersion: 0,
      notifyDemoDataReset: jest.fn(),
    });

    render(<ChatScreen />);

    expect(await screen.findByText("工作台暂时不可用")).toBeTruthy();
    expect(screen.getAllByText(FRONTLINE_STATUS_COPY.networkUnavailable).length).toBeGreaterThan(0);
  });

  it("shows general workbench-unavailable hint for non-network bootstrap failures", async () => {
    mockedUseSessionStream.mockReturnValue({
      sessionId: "sess_1",
      sessionTitle: "Store shift session",
      connectionState: "error",
      bootstrapError: "Failed to bootstrap session",
      retryBootstrap: jest.fn(),
      lastEvent: null,
      recentEvents: [],
      dataResetVersion: 0,
      notifyDemoDataReset: jest.fn(),
    });

    render(<ChatScreen />);

    expect(await screen.findByText("工作台暂时不可用")).toBeTruthy();
    expect(screen.getAllByText(FRONTLINE_STATUS_COPY.workbenchUnavailable).length).toBeGreaterThan(0);
  });

  it("shows friendly unavailable titles for shared chat states", async () => {
    mockedUseSessionStream.mockReturnValue({
      sessionId: "sess_1",
      sessionTitle: "Store shift session",
      connectionState: "error",
      bootstrapError: null,
      retryBootstrap: jest.fn(),
      lastEvent: null,
      recentEvents: [],
      dataResetVersion: 0,
      notifyDemoDataReset: jest.fn(),
    });
    mockedUseSessionMessagesQuery.mockReturnValue({
      data: [],
      isLoading: false,
      error: "Request failed",
      refresh: jest.fn(),
    });
    mockedUseChatPendingConfirmationsQuery.mockReturnValue({
      data: [],
      isLoading: false,
      error: "Request failed",
      refresh: jest.fn(),
    });

    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.getByText("连接受限")).toBeTruthy();
      expect(screen.getByText("消息列表暂时不可用")).toBeTruthy();
      expect(screen.getByText("待确认事项暂时不可用")).toBeTruthy();
      expect(screen.getByText("提交仍可继续，但结果刷新可能延迟。")).toBeTruthy();
      expect(screen.getAllByText("Request failed").length).toBeGreaterThanOrEqual(2);
    });
  });

  it("highlights the matching task when opened from a dashboard intent", async () => {
    render(
      <ChatScreen
        route={{
          key: "workbench",
          name: ROOT_TABS.workbench,
          params: { initialIntent: "voice-query" },
        } as never}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("从这里发起语音查货")).toBeTruthy();
      expect(screen.getByTestId("guided-pill-voice").props.accessibilityState.selected).toBe(true);
      const selectedStyleProp = screen.getByTestId("guided-pill-voice").props.style;
      const selectedStyles = Array.isArray(selectedStyleProp) ? selectedStyleProp : [selectedStyleProp];
      expect(selectedStyles.some((entry: { borderColor?: string } | null) => entry?.borderColor === "#0071e3")).toBe(true);
    });
  });

  it("consumes dashboard intent so a later plain revisit returns to default workbench state", async () => {
    let onBlur: (() => void) | null = null;
    const route = {
      key: "workbench",
      name: ROOT_TABS.workbench,
      params: { initialIntent: "voice-query" },
    };
    const navigation = {
      setParams: jest.fn((params: { initialIntent?: "voice-query" | "photo-stock-in" | "receipt-entry" | "pending-confirmations" }) => {
        route.params = { ...route.params, ...params };
      }),
      addListener: jest.fn((event: string, listener: () => void) => {
        if (event === "blur") {
          onBlur = listener;
        }
        return jest.fn();
      }),
    };

    const { rerender } = render(
      <ChatScreen
        {...({
          route,
          navigation,
        } as never)}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("guided-pill-voice").props.accessibilityState.selected).toBe(true);
    });

    await waitFor(() => {
      expect(navigation.setParams).toHaveBeenCalledWith({ initialIntent: undefined });
    });

    act(() => {
      onBlur?.();
    });
    rerender(
      <ChatScreen
        {...({
          route,
          navigation,
        } as never)}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("guided-pill-voice").props.accessibilityState.selected).toBe(false);
    });
  });

  it("shows a refresh affordance when connection is limited", async () => {
    mockedUseSessionStream.mockReturnValue({
      sessionId: "sess_1",
      sessionTitle: "Store shift session",
      connectionState: "disconnected",
      bootstrapError: null,
      retryBootstrap: jest.fn(),
      lastEvent: null,
      recentEvents: [],
      dataResetVersion: 0,
      notifyDemoDataReset: jest.fn(),
    });

    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.getByText("连接受限")).toBeTruthy();
      expect(screen.getByText("立即刷新")).toBeTruthy();
    });
  });

  it("retries bootstrap when pressing the bootstrap-error recovery action", async () => {
    const retryBootstrap = jest.fn();

    mockedUseSessionStream.mockReturnValue({
      sessionId: "sess_1",
      sessionTitle: "Store shift session",
      connectionState: "error",
      bootstrapError: "Failed to bootstrap session",
      retryBootstrap,
      lastEvent: null,
      recentEvents: [],
      dataResetVersion: 0,
      notifyDemoDataReset: jest.fn(),
    });

    render(<ChatScreen />);

    fireEvent.press(await screen.findByText("重试连接"));

    expect(retryBootstrap).toHaveBeenCalledTimes(1);
  });
});
