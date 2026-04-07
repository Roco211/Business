import { fireEvent, render, screen } from "@testing-library/react-native";

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

  it("shows readable login hero copy and keeps environment details secondary", () => {
    render(<LoginScreen />);

    expect(screen.getByText("门店试运行")).toBeTruthy();
    expect(screen.getByText("先确认连接，再开始今日入库")).toBeTruthy();
    expect(screen.getByText("登录后即可继续语音、拍照和票据入账")).toBeTruthy();
    expect(screen.getByText("环境地址仅供排查，日常可直接登录。")).toBeTruthy();
    expect(screen.getByText("\u767b\u5f55")).toBeTruthy();
    expect(screen.getByText("\u6682\u65f6\u65e0\u6cd5\u767b\u5f55")).toBeTruthy();
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

    expect(screen.getByText("\u6b63\u5728\u767b\u5f55...")).toBeTruthy();
    fireEvent.press(screen.getByRole("button"));
    expect(mockSubmitLogin).not.toHaveBeenCalled();
  });
});
