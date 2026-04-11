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

    expect(screen.getByText("提交后会自动同步")).toBeTruthy();
    expect(screen.getByText("系统会代你发起当前任务，并在下方返回处理结果。")).toBeTruthy();

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

  it("shows a stock-in photo label that matches the submitted action", () => {
    mockedUseSendVoiceDemoMutation.mockReturnValue({
      isSubmitting: false,
      error: null,
      submitVoiceDemo: jest.fn(),
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

    render(<GuidedEntryDock sessionId="sess_1" onSubmitted={jest.fn()} highlightedIntent="photo-stock-in" />);

    expect(screen.getByText("拍照入库")).toBeTruthy();
  });

  it("shows session-unavailable guidance and keeps guided actions disabled when no session exists", () => {
    const submitVoiceDemo = jest.fn();
    const submitImageDemo = jest.fn();
    const submitReceiptDemo = jest.fn();

    mockedUseSendVoiceDemoMutation.mockReturnValue({
      isSubmitting: false,
      error: null,
      submitVoiceDemo,
    } as never);
    mockedUseSendImageDemoMutation.mockReturnValue({
      isSubmitting: false,
      error: null,
      submitImageDemo,
    } as never);
    mockedUseSendReceiptDemoMutation.mockReturnValue({
      isSubmitting: false,
      error: null,
      submitReceiptDemo,
    } as never);

    render(<GuidedEntryDock sessionId={null} onSubmitted={jest.fn()} />);

    expect(screen.getByText("会话暂不可用")).toBeTruthy();
    expect(screen.getByText("会话尚未就绪，暂时不能提交演练请求。")).toBeTruthy();

    expect(screen.getByTestId("guided-pill-voice").props.accessibilityState.disabled).toBe(true);
    expect(screen.getByTestId("guided-pill-photo").props.accessibilityState.disabled).toBe(true);
    expect(screen.getByTestId("guided-pill-receipt").props.accessibilityState.disabled).toBe(true);

    fireEvent.press(screen.getByTestId("guided-pill-voice"));
    fireEvent.press(screen.getByTestId("guided-pill-photo"));
    fireEvent.press(screen.getByTestId("guided-pill-receipt"));

    expect(submitVoiceDemo).not.toHaveBeenCalled();
    expect(submitImageDemo).not.toHaveBeenCalled();
    expect(submitReceiptDemo).not.toHaveBeenCalled();
    expect(screen.queryByText("提交失败")).toBeNull();
  });

  it("shows the latest active-entry error when different guided entries fail sequentially", async () => {
    let voiceError: string | null = null;
    let imageError: string | null = null;

    const submitVoiceDemo = jest.fn().mockImplementation(async () => {
      voiceError = "voice demo failed";
      return null;
    });
    const submitImageDemo = jest.fn().mockImplementation(async () => {
      imageError = "photo demo failed";
      return null;
    });

    mockedUseSendVoiceDemoMutation.mockReturnValue({
      isSubmitting: false,
      get error() {
        return voiceError;
      },
      submitVoiceDemo,
    } as never);
    mockedUseSendImageDemoMutation.mockReturnValue({
      isSubmitting: false,
      get error() {
        return imageError;
      },
      submitImageDemo,
    } as never);
    mockedUseSendReceiptDemoMutation.mockReturnValue({
      isSubmitting: false,
      error: null,
      submitReceiptDemo: jest.fn(),
    } as never);

    render(<GuidedEntryDock sessionId="sess_1" onSubmitted={jest.fn()} />);

    fireEvent.press(screen.getByTestId("guided-pill-voice"));

    await waitFor(() => {
      expect(screen.getByText("voice demo failed")).toBeTruthy();
    });

    fireEvent.press(screen.getByTestId("guided-pill-photo"));

    await waitFor(() => {
      expect(screen.getByText("photo demo failed")).toBeTruthy();
    });
  });
});
