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

  it("shows readable login hero copy and keeps environment details secondary before login fails", () => {
    mockUseLoginMutation.mockReturnValue({
      isSubmitting: false,
      error: null,
      submitLogin: mockSubmitLogin,
    });

    render(<LoginScreen />);

    expect(screen.getByText("\u95e8\u5e97\u8bd5\u8fd0\u884c")).toBeTruthy();
    expect(screen.getByText("\u5148\u786e\u8ba4\u8fde\u63a5\uff0c\u518d\u5f00\u59cb\u4eca\u65e5\u5165\u5e93")).toBeTruthy();
    expect(screen.getByText("\u767b\u5f55\u540e\u5373\u53ef\u7ee7\u7eed\u8bed\u97f3\u3001\u62cd\u7167\u548c\u7968\u636e\u5165\u8d26")).toBeTruthy();
    expect(screen.getByText("\u73af\u5883\u5730\u5740\u4ec5\u4f9b\u6392\u67e5\uff0c\u65e5\u5e38\u53ef\u76f4\u63a5\u767b\u5f55\u3002")).toBeTruthy();
    expect(screen.getByText("\u8fde\u63a5\u6392\u67e5")).toBeTruthy();
    expect(screen.getByText("\u767b\u5f55")).toBeTruthy();
    expect(screen.queryByText("\u6682\u65f6\u65e0\u6cd5\u767b\u5f55")).toBeNull();
    expect(screen.queryByText("\u5f53\u524d\u65e0\u6cd5\u8fde\u63a5\u95e8\u5e97\u670d\u52a1\uff0c\u8bf7\u68c0\u67e5\u7f51\u7edc\u540e\u91cd\u8bd5\u3002")).toBeNull();
    expect(screen.queryByText("http://10.0.2.2:8001")).toBeNull();
    expect(screen.queryByText(/http:\/\/192\.168\.1\.4:8001/i)).toBeNull();
  });

  it("shows troubleshooting details with the current service address after login fails", () => {
    render(<LoginScreen />);

    expect(screen.getByText("\u8fde\u63a5\u6392\u67e5")).toBeTruthy();
    expect(screen.getByText("\u5f53\u524d\u95e8\u5e97\u670d\u52a1")).toBeTruthy();
    expect(screen.getByText("http://10.0.2.2:8001")).toBeTruthy();
    expect(screen.getByText("\u2022 \u68c0\u67e5\u672c\u673a\u6216\u95e8\u5e97\u670d\u52a1\u662f\u5426\u5df2\u542f\u52a8")).toBeTruthy();
    expect(screen.getByText("\u2022 \u82e5\u5728\u5b89\u5353\u6a21\u62df\u5668\u4e2d\u8fd0\u884c\uff0c\u8bf7\u786e\u8ba4\u540e\u7aef\u4f7f\u7528 10.0.2.2")).toBeTruthy();
    expect(screen.getByText("\u2022 \u82e5\u662f\u771f\u673a\u6d4b\u8bd5\uff0c\u8bf7\u786e\u4fdd\u8bbe\u5907\u4e0e\u5f00\u53d1\u673a\u5728\u540c\u4e00\u7f51\u7edc")).toBeTruthy();
  });

  it("submits current email and password when pressing login", () => {
    render(<LoginScreen />);

    fireEvent.changeText(screen.getByLabelText("\u90ae\u7bb1"), "boss@example.com");
    fireEvent.changeText(screen.getByLabelText("\u5bc6\u7801"), "new-pass-123");
    fireEvent.press(screen.getByRole("button", { name: "\u767b\u5f55" }));

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
    fireEvent.press(screen.getByRole("button", { name: "\u6b63\u5728\u767b\u5f55..." }));
    expect(mockSubmitLogin).not.toHaveBeenCalled();
  });

  it("keeps the keyboard container content-sized so Android does not collapse the login form", () => {
    const view = render(<LoginScreen />);

    expect(view.UNSAFE_getByType(KeyboardAvoidingView).props.style).not.toEqual(
      expect.objectContaining({ flex: 1 }),
    );
  });
});
