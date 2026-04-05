import { render, screen } from "@testing-library/react-native";

import App from "../App";


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


test("renders the three primary screen labels", () => {
  render(<App />);

  expect(screen.getAllByText("工作台").length).toBeGreaterThan(0);
  expect(screen.getAllByText("工作群").length).toBeGreaterThan(0);
  expect(screen.getAllByText("账本").length).toBeGreaterThan(0);
});
