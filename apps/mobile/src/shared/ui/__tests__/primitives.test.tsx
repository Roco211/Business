import { fireEvent, render, screen } from "@testing-library/react-native";

import {
  AppScreen,
  AppTextField,
  DebugDisclosure,
  EmptyState,
  InlineNotice,
  PillActionButton,
  PrimaryButton,
  StatusBadge,
} from "../index";

describe("shared ui primitives", () => {
  it("shows loading copy for PrimaryButton", () => {
    render(<PrimaryButton label="登录" loadingLabel="登录中..." loading onPress={() => undefined} />);

    expect(screen.getByText("登录中...")).toBeTruthy();
  });

  it("renders AppTextField label and error copy", () => {
    render(
      <AppTextField
        label="邮箱"
        value="owner@example.com"
        onChangeText={() => undefined}
        error="请输入有效邮箱"
      />,
    );

    expect(screen.getByText("邮箱")).toBeTruthy();
    expect(screen.getByText("请输入有效邮箱")).toBeTruthy();
  });

  it("hides and reveals DebugDisclosure content", () => {
    render(
      <DebugDisclosure title="调试工具">
        <InlineNotice tone="neutral" message="Demo reset lives here" />
      </DebugDisclosure>,
    );

    expect(screen.queryByText("Demo reset lives here")).toBeNull();

    fireEvent.press(screen.getByText("调试工具"));

    expect(screen.getByText("Demo reset lives here")).toBeTruthy();
  });

  it("renders AppScreen with StatusBadge and EmptyState", () => {
    render(
      <AppScreen title="今天">
        <StatusBadge tone="warning" label="待确认" />
        <EmptyState title="暂无数据" description="先从语音或拍照开始。" />
      </AppScreen>,
    );

    expect(screen.getByText("今天")).toBeTruthy();
    expect(screen.getByText("待确认")).toBeTruthy();
    expect(screen.getByText("暂无数据")).toBeTruthy();
    expect(screen.getByText("先从语音或拍照开始。")).toBeTruthy();
  });

  it("renders PillActionButton label", () => {
    render(<PillActionButton label="语音" onPress={() => undefined} />);

    expect(screen.getByText("语音")).toBeTruthy();
  });
});
