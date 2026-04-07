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

  it("renders branded hierarchy and inline network message", () => {
    render(<LoginScreen />);

    expect(screen.getByText("\u95e8\u5e97\u5e93\u5b58\u52a9\u624b")).toBeTruthy();
    expect(screen.getByText("\u8bed\u97f3\u3001\u62cd\u7167\u3001\u7968\u636e\u7edf\u4e00\u5165\u8d26")).toBeTruthy();
    expect(screen.getByText("\u767b\u5f55")).toBeTruthy();
    expect(screen.getByText(/Cannot reach API at http:\/\/.+:8001 \(Network request failed\)/)).toBeTruthy();
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

    expect(screen.getByText("\u767b\u5f55\u4e2d...")).toBeTruthy();
    fireEvent.press(screen.getByRole("button"));
    expect(mockSubmitLogin).not.toHaveBeenCalled();
  });
});
