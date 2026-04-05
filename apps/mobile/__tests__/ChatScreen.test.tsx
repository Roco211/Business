import { render, screen } from "@testing-library/react-native";

import ChatScreen from "../src/features/chat/screens/ChatScreen";


jest.mock("../src/shared/session/useSessionStream", () => ({
  useSessionStream: () => ({
    sessionId: "sess_default",
    sessionTitle: "数字员工工作群",
    connectionState: "connected",
    bootstrapError: null,
    lastEvent: {
      event_id: "evt_message_created",
      seq: 3,
      event_type: "message.created",
      session_id: "sess_default",
      task_run_id: "task_1",
      message_id: "msg_1",
      occurred_at: "2026-04-05T12:00:00.000Z",
      data: {
        preview_text: "restock cola",
      },
    },
    recentEvents: [
      {
        event_id: "evt_message_created",
        seq: 3,
        event_type: "message.created",
        session_id: "sess_default",
        task_run_id: "task_1",
        message_id: "msg_1",
        occurred_at: "2026-04-05T12:00:00.000Z",
        data: {
          preview_text: "restock cola",
        },
      },
    ],
  }),
}));


describe("ChatScreen", () => {
  it("renders session state and recent session events", () => {
    render(<ChatScreen />);

    expect(screen.getByText("数字员工工作群")).toBeTruthy();
    expect(screen.getByText("connected")).toBeTruthy();
    expect(screen.getByText("message.created")).toBeTruthy();
    expect(screen.getByText("restock cola")).toBeTruthy();
  });
});
