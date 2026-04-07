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
      expect(screen.getByText("发送更新")).toBeTruthy();
      expect(screen.getByText("调试工具")).toBeTruthy();
      expect(screen.getByText("展开")).toBeTruthy();
    });
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
});
