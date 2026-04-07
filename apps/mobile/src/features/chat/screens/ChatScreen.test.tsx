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
      submitMessage: jest.fn().mockResolvedValue({ data: { message_id: "msg_2", task_run_id: "task_2", status: "created" } }),
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it("renders guided workbench header and dock", async () => {
    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.getByText("Chat Workbench")).toBeTruthy();
      expect(screen.getByText("Store shift session")).toBeTruthy();
      expect(screen.getByText("Guided entry")).toBeTruthy();
      expect(screen.getByText("Voice")).toBeTruthy();
      expect(screen.getByText("Photo")).toBeTruthy();
      expect(screen.getByText("Receipt")).toBeTruthy();
      expect(screen.getByPlaceholderText("Describe your request")).toBeTruthy();
      expect(screen.getByText("Send update")).toBeTruthy();
    });
  });

  it("hides legacy media demos until debug disclosure is opened", async () => {
    render(<ChatScreen />);

    await waitFor(() => {
      expect(screen.queryByText("Voice Query Demo")).toBeNull();
    });

    fireEvent.press(screen.getByLabelText("Debug tools"));

    await waitFor(() => {
      expect(screen.getByText("Voice Query Demo")).toBeTruthy();
    });
  });
});
