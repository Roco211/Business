import { render, screen } from "@testing-library/react-native";

import App from "../App";
import { clearAuthSession, setAuthSession } from "../src/shared/auth/authStore";

jest.mock("../src/features/dashboard/screens/DashboardScreen", () => {
  const ReactNative = require("react-native");
  return function MockDashboardScreen() {
    return <ReactNative.Text>Mock Dashboard Screen</ReactNative.Text>;
  };
});

jest.mock("../src/features/chat/screens/ChatScreen", () => {
  const ReactNative = require("react-native");
  return function MockChatScreen() {
    return <ReactNative.Text>Mock Chat Screen</ReactNative.Text>;
  };
});

jest.mock("../src/features/ledger/screens/LedgerScreen", () => {
  const ReactNative = require("react-native");
  return function MockLedgerScreen() {
    return <ReactNative.Text>Mock Ledger Screen</ReactNative.Text>;
  };
});

jest.mock("../src/shared/session/SessionStreamProvider", () => ({
  SessionStreamProvider: ({ children }: { children: React.ReactNode }) => children,
}));

beforeEach(() => {
  clearAuthSession();
});

afterEach(() => {
  clearAuthSession();
});

test("renders login screen before auth session exists", () => {
  render(<App />);

  expect(screen.getAllByText("登录").length).toBeGreaterThan(0);
});

test("renders the three primary screen labels when already authenticated", () => {
  setAuthSession({
    accessToken: "token_existing",
    tokenType: "Bearer",
    ownerActorId: "owner_default",
    shopId: "shop_default",
    shopName: "Demo Shop",
  });

  render(<App />);

  expect(screen.getByText("Mock Dashboard Screen")).toBeTruthy();
  expect(screen.getAllByRole("button").length).toBeGreaterThanOrEqual(3);
});
