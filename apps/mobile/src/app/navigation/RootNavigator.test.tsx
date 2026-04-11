import { act, render, screen } from "@testing-library/react-native";

import { clearAuthSession, setAuthSession } from "../../shared/auth/authStore";
import RootNavigator from "./RootNavigator";
import { ROOT_TAB_LABELS } from "./rootTabConfig";

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

  it("shows clean tab labels for authenticated users", () => {
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

    expect(screen.getByText(ROOT_TAB_LABELS.dashboard)).toBeTruthy();
    expect(screen.getByText(ROOT_TAB_LABELS.workbench)).toBeTruthy();
    expect(screen.getByText(ROOT_TAB_LABELS.ledger)).toBeTruthy();
    expect(screen.queryByText("\\u9996\\u9875")).toBeNull();
    expect(screen.queryByText("\\u5de5\\u4f5c\\u53f0")).toBeNull();
    expect(screen.queryByText("\\u53f0\\u8d26")).toBeNull();
  });
});
