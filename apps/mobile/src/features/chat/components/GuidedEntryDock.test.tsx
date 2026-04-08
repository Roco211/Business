import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import { useSendImageDemoMutation } from "../hooks/useSendImageDemoMutation";
import { useSendReceiptDemoMutation } from "../hooks/useSendReceiptDemoMutation";
import { useSendVoiceDemoMutation } from "../hooks/useSendVoiceDemoMutation";
import { GuidedEntryDock } from "./GuidedEntryDock";

jest.mock("../hooks/useSendVoiceDemoMutation");
jest.mock("../hooks/useSendImageDemoMutation");
jest.mock("../hooks/useSendReceiptDemoMutation");

const mockedUseSendVoiceDemoMutation = useSendVoiceDemoMutation as jest.MockedFunction<
  typeof useSendVoiceDemoMutation
>;
const mockedUseSendImageDemoMutation = useSendImageDemoMutation as jest.MockedFunction<
  typeof useSendImageDemoMutation
>;
const mockedUseSendReceiptDemoMutation = useSendReceiptDemoMutation as jest.MockedFunction<
  typeof useSendReceiptDemoMutation
>;

describe("GuidedEntryDock", () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it("shows local submitting and accepted feedback for a voice rehearsal request", async () => {
    const onSubmitted = jest.fn();

    mockedUseSendVoiceDemoMutation.mockReturnValue({
      isSubmitting: false,
      error: null,
      submitVoiceDemo: jest.fn().mockResolvedValue({ data: { task_run_id: "task_1" } }),
    } as never);
    mockedUseSendImageDemoMutation.mockReturnValue({
      isSubmitting: false,
      error: null,
      submitImageDemo: jest.fn(),
    } as never);
    mockedUseSendReceiptDemoMutation.mockReturnValue({
      isSubmitting: false,
      error: null,
      submitReceiptDemo: jest.fn(),
    } as never);

    render(<GuidedEntryDock sessionId="sess_1" onSubmitted={onSubmitted} highlightedIntent="voice-query" />);

    expect(screen.getByText("当前为流程演练，会提交预设样例请求。")).toBeTruthy();

    fireEvent.press(screen.getByTestId("guided-pill-voice"));

    expect(await screen.findByText("正在提交语音查货请求")).toBeTruthy();

    await waitFor(() => {
      expect(screen.getByText("已提交")).toBeTruthy();
      expect(screen.getByText("正在处理中，如需复核请查看下方的待确认区域。")).toBeTruthy();
      expect(onSubmitted).toHaveBeenCalledTimes(1);
    });
  });

  it("submits stock-in demo kind when pressing the photo stock-in entry", async () => {
    const onSubmitted = jest.fn();
    const submitImageDemo = jest.fn().mockResolvedValue({ data: { task_run_id: "task_2" } });

    mockedUseSendVoiceDemoMutation.mockReturnValue({
      isSubmitting: false,
      error: null,
      submitVoiceDemo: jest.fn(),
    } as never);
    mockedUseSendImageDemoMutation.mockReturnValue({
      isSubmitting: false,
      error: null,
      submitImageDemo,
    } as never);
    mockedUseSendReceiptDemoMutation.mockReturnValue({
      isSubmitting: false,
      error: null,
      submitReceiptDemo: jest.fn(),
    } as never);

    render(<GuidedEntryDock sessionId="sess_1" onSubmitted={onSubmitted} highlightedIntent="photo-stock-in" />);

    fireEvent.press(screen.getByTestId("guided-pill-photo"));

    expect(await screen.findByText("正在提交拍照入库请求")).toBeTruthy();

    await waitFor(() => {
      expect(submitImageDemo).toHaveBeenCalledWith("stock_in");
      expect(screen.getByText("已提交")).toBeTruthy();
      expect(onSubmitted).toHaveBeenCalledTimes(1);
    });
  });
});
