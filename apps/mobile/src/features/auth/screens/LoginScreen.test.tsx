import { render, screen } from "@testing-library/react-native";

import { useLoginMutation } from "../hooks/useLoginMutation";
import LoginScreen from "./LoginScreen";

jest.mock("../hooks/useLoginMutation", () => ({
  useLoginMutation: jest.fn(),
}));

describe("LoginScreen", () => {
  const mockUseLoginMutation = useLoginMutation as jest.MockedFunction<typeof useLoginMutation>;

  beforeEach(() => {
    mockUseLoginMutation.mockReturnValue({
      isSubmitting: false,
      error: "Cannot reach API at http://192.168.1.4:8001 (Network request failed)",
      submitLogin: jest.fn(),
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
    expect(
      screen.getByText("Cannot reach API at http://192.168.1.4:8001 (Network request failed)"),
    ).toBeTruthy();
  });
});
