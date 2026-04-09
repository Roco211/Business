import { fireEvent, render, screen } from "@testing-library/react-native";
import { KeyboardAvoidingView } from "react-native";

import { useLoginMutation } from "../hooks/useLoginMutation";
import LoginScreen from "./LoginScreen";

jest.mock("../hooks/useLoginMutation", () => ({
  useLoginMutation: jest.fn(),
}));

describe("LoginScreen", () => {
  const mockUseLoginMutation = useLoginMutation as jest.MockedFunction<typeof useLoginMutation>;
  const mockSubmitLogin = jest.fn();

  beforeEach(() => {
    mockSubmitLogin.mockReset();
    mockUseLoginMutation.mockReturnValue({
      isSubmitting: false,
      error: "Cannot reach API at http://192.168.1.4:8001 (Network request failed)",
      submitLogin: mockSubmitLogin,
    });
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it("shows brand-first login copy and keeps connection failures readable", () => {
    render(<LoginScreen />);

    expect(screen.getByText("门店助理")).toBeTruthy();
    expect(screen.getByText("轻松看店、理货、记账")).toBeTruthy();
    expect(screen.getByText("先看店铺概览，再处理今天的门店事项。")).toBeTruthy();
    expect(screen.getByText("当前测试环境使用邮箱登录，连接异常时会在下方直接提示。")).toBeTruthy();
    expect(screen.getByText("进入门店助理")).toBeTruthy();
    expect(screen.getByText("暂时无法进入")).toBeTruthy();
    expect(screen.getByText("\u5f53\u524d\u65e0\u6cd5\u8fde\u63a5\u95e8\u5e97\u670d\u52a1\uff0c\u8bf7\u68c0\u67e5\u7f51\u7edc\u540e\u91cd\u8bd5\u3002")).toBeTruthy();
    expect(screen.queryByText("http://10.0.2.2:8001")).toBeNull();
    expect(screen.queryByText(/http:\/\/192\.168\.1\.4:8001/i)).toBeNull();
  });

  it("submits current email and password when pressing login", () => {
    render(<LoginScreen />);

    fireEvent.changeText(screen.getByLabelText("\u90ae\u7bb1"), "boss@example.com");
    fireEvent.changeText(screen.getByLabelText("\u5bc6\u7801"), "new-pass-123");
    fireEvent.press(screen.getByRole("button"));

    expect(mockSubmitLogin).toHaveBeenCalledWith("boss@example.com", "new-pass-123");
  });

  it("shows loading copy and disables login button while submitting", () => {
    mockUseLoginMutation.mockReturnValue({
      isSubmitting: true,
      error: null,
      submitLogin: mockSubmitLogin,
    });

    render(<LoginScreen />);

    expect(screen.getByText("\u6b63\u5728\u8fdb\u5165...")).toBeTruthy();
    fireEvent.press(screen.getByRole("button"));
    expect(mockSubmitLogin).not.toHaveBeenCalled();
  });

  it("keeps the keyboard container content-sized so Android does not collapse the login form", () => {
    const view = render(<LoginScreen />);

    expect(view.UNSAFE_getByType(KeyboardAvoidingView).props.style).not.toEqual(
      expect.objectContaining({ flex: 1 }),
    );
  });
});
