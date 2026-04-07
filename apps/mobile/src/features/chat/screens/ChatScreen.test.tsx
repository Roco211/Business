import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import ChatScreen from "./ChatScreen";
import { useChatPendingConfirmationsQuery } from "../hooks/useChatPendingConfirmationsQuery";
import { useSendMessageMutation } from "../hooks/useSendMessageMutation";
import { useSessionMessagesQuery } from "../hooks/useSessionMessagesQuery";
import { useSessionStream } from "../../../shared/session/useSessionStream";

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

  it("renders guided workbench header and dock", async () => {
    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.getByText("聊天工作台")).toBeTruthy();
      expect(screen.getByText("Store shift session")).toBeTruthy();
      expect(screen.getByText("连接状态")).toBeTruthy();
      expect(screen.getByText("已连接")).toBeTruthy();
      expect(screen.getByText("引导入口")).toBeTruthy();
      expect(screen.getByText("语音")).toBeTruthy();
      expect(screen.getByText("拍照")).toBeTruthy();
      expect(screen.getByText("票据")).toBeTruthy();
      expect(screen.getByText("店主")).toBeTruthy();
      expect(screen.getByText("类型：文本")).toBeTruthy();
      expect(screen.getByPlaceholderText("描述你的请求")).toBeTruthy();
      expect(screen.getByText("发送消息")).toBeTruthy();
      expect(screen.getByText("调试工具")).toBeTruthy();
      expect(screen.getByText("展开")).toBeTruthy();
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

  it("hides legacy media demos until debug disclosure is opened", async () => {
    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.queryByText("Voice Query Demo")).toBeNull();
    });

    fireEvent.press(screen.getByLabelText("调试工具"));

    await waitFor(() => {
      expect(screen.getByText("Voice Query Demo")).toBeTruthy();
      expect(screen.getByText("收起")).toBeTruthy();
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
      lastEvent: null,
      recentEvents: [],
      dataResetVersion: 0,
      notifyDemoDataReset: jest.fn(),
    });

    render(<ChatScreen />);

    expect(await screen.findByText("工作台暂时不可用")).toBeTruthy();
    expect(screen.getAllByText("当前无法连接门店服务，请检查网络后重试。").length).toBeGreaterThan(0);
  });

  it("shows general workbench-unavailable hint for non-network bootstrap failures", async () => {
    mockedUseSessionStream.mockReturnValue({
      sessionId: "sess_1",
      sessionTitle: "Store shift session",
      connectionState: "error",
      bootstrapError: "Failed to bootstrap session",
      lastEvent: null,
      recentEvents: [],
      dataResetVersion: 0,
      notifyDemoDataReset: jest.fn(),
    });

    render(<ChatScreen />);

    expect(await screen.findByText("\u5de5\u4f5c\u53f0\u6682\u65f6\u4e0d\u53ef\u7528")).toBeTruthy();
    expect(
      screen.getAllByText("\u5de5\u4f5c\u53f0\u6682\u65f6\u4e0d\u53ef\u7528\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5\u3002").length,
    ).toBeGreaterThan(0);
    expect(screen.queryByText("\u5f53\u524d\u65e0\u6cd5\u8fde\u63a5\u95e8\u5e97\u670d\u52a1\uff0c\u8bf7\u68c0\u67e5\u7f51\u7edc\u540e\u91cd\u8bd5\u3002")).toBeNull();
  });

  it("shows friendly unavailable titles for shared chat states", async () => {
    mockedUseSessionStream.mockReturnValue({
      sessionId: "sess_1",
      sessionTitle: "Store shift session",
      connectionState: "error",
      bootstrapError: null,
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
      expect(screen.getByText("实时更新受限，执行操作后仍会触发手动刷新。")).toBeTruthy();
      expect(screen.getAllByText("Request failed").length).toBeGreaterThanOrEqual(2);
    });
  });
});
