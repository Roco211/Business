import { fireEvent, render, screen } from "@testing-library/react-native";
import { KeyboardAvoidingView } from "react-native";

import { getApiBaseUrl } from "../../../shared/api/client";
import { useLoginMutation } from "../hooks/useLoginMutation";
import LoginScreen from "./LoginScreen";

jest.mock("../../../shared/api/client", () => ({
  getApiBaseUrl: jest.fn(),
}));

jest.mock("../hooks/useLoginMutation", () => ({
  useLoginMutation: jest.fn(),
}));

describe("LoginScreen", () => {
  const mockGetApiBaseUrl = getApiBaseUrl as jest.MockedFunction<typeof getApiBaseUrl>;
  const mockUseLoginMutation = useLoginMutation as jest.MockedFunction<typeof useLoginMutation>;
  const mockSubmitLogin = jest.fn();

  beforeEach(() => {
    mockGetApiBaseUrl.mockReturnValue("http://10.0.2.2:8001");
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

  it("shows brand-first login copy and keeps connection details tucked away before failures", () => {
    mockUseLoginMutation.mockReturnValue({
      isSubmitting: false,
      error: null,
      submitLogin: mockSubmitLogin,
    });

    render(<LoginScreen />);

    expect(screen.getByText("门店助理")).toBeTruthy();
    expect(screen.getByText("轻松看店、理货、记账")).toBeTruthy();
    expect(screen.getByText("先看店铺概览，再处理今天的门店事项。")).toBeTruthy();
    expect(screen.getByText("进入当前门店")).toBeTruthy();
    expect(screen.getByText("当前测试环境使用邮箱登录，连接异常时会在下方直接提示。")).toBeTruthy();
    expect(screen.getByText("连接排查")).toBeTruthy();
    expect(screen.getByText("进入门店助理")).toBeTruthy();
    expect(screen.queryByText("暂时无法进入")).toBeNull();
    expect(screen.queryByText("http://10.0.2.2:8001")).toBeNull();
    expect(screen.queryByText(/http:\/\/192\.168\.1\.4:8001/i)).toBeNull();
  });

  it("shows troubleshooting details with the current service address after login fails", () => {
    render(<LoginScreen />);

    expect(screen.getByText("暂时无法进入")).toBeTruthy();
    expect(screen.getByText("连接排查")).toBeTruthy();
    expect(screen.getByText("当前门店服务")).toBeTruthy();
    expect(screen.getByText("http://10.0.2.2:8001")).toBeTruthy();
    expect(screen.getByText("• 检查本机或门店服务是否已启动")).toBeTruthy();
    expect(screen.getByText("• 若在安卓模拟器中运行，请确认后端使用 10.0.2.2")).toBeTruthy();
    expect(screen.getByText("• 若是真机测试，请确保设备与开发机在同一网络")).toBeTruthy();
  });

  it("submits current email and password when pressing login", () => {
    render(<LoginScreen />);

    fireEvent.changeText(screen.getByLabelText("邮箱"), "boss@example.com");
    fireEvent.changeText(screen.getByLabelText("密码"), "new-pass-123");
    fireEvent.press(screen.getByRole("button", { name: "进入门店助理" }));

    expect(mockSubmitLogin).toHaveBeenCalledWith("boss@example.com", "new-pass-123");
  });

  it("shows loading copy and disables login button while submitting", () => {
    mockUseLoginMutation.mockReturnValue({
      isSubmitting: true,
      error: null,
      submitLogin: mockSubmitLogin,
    });

    render(<LoginScreen />);

    expect(screen.getByText("正在进入...")).toBeTruthy();
    fireEvent.press(screen.getByRole("button", { name: "正在进入..." }));
    expect(mockSubmitLogin).not.toHaveBeenCalled();
  });

  it("keeps the keyboard container content-sized so Android does not collapse the login form", () => {
    const view = render(<LoginScreen />);

    expect(view.UNSAFE_getByType(KeyboardAvoidingView).props.style).not.toEqual(
      expect.objectContaining({ flex: 1 }),
    );
  });
});
