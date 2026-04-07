import { act, render, screen } from "@testing-library/react-native";

import { clearAuthSession, setAuthSession } from "../../shared/auth/authStore";
import RootNavigator from "./RootNavigator";

jest.mock("../../features/dashboard/screens/DashboardScreen", () => {
  const ReactNative = require("react-native");
  return function MockDashboardScreen() {
    return <ReactNative.Text>Mock Dashboard Screen</ReactNative.Text>;
  };
});

jest.mock("../../features/chat/screens/ChatScreen", () => {
  const ReactNative = require("react-native");
  return function MockChatScreen() {
    return <ReactNative.Text>Mock Chat Screen</ReactNative.Text>;
  };
});

jest.mock("../../features/ledger/screens/LedgerScreen", () => {
  const ReactNative = require("react-native");
  return function MockLedgerScreen() {
    return <ReactNative.Text>Mock Ledger Screen</ReactNative.Text>;
  };
});

jest.mock("../../shared/session/SessionStreamProvider", () => ({
  SessionStreamProvider: ({ children }: { children: React.ReactNode }) => children,
}));

describe("RootNavigator", () => {
  beforeEach(() => {
    act(() => {
      clearAuthSession();
    });
  });

  afterEach(() => {
    act(() => {
      clearAuthSession();
    });
  });

  it("shows updated tab labels when auth session exists", () => {
    act(() => {
      setAuthSession({
        accessToken: "token_existing",
        tokenType: "Bearer",
        ownerActorId: "owner_default",
        shopId: "shop_default",
        shopName: "Demo Shop",
      });
    });

    render(<RootNavigator />);

    expect(screen.getByLabelText(/\\u9996\\u9875/)).toBeTruthy();
    expect(screen.getByLabelText(/\\u5de5\\u4f5c\\u53f0/)).toBeTruthy();
    expect(screen.getByLabelText(/\\u53f0\\u8d26/)).toBeTruthy();
  });
});
