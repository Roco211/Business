import { fireEvent, render, screen } from "@testing-library/react-native";
import { Pressable, StyleSheet } from "react-native";

import {
  AppScreen,
  AppTextField,
  DebugDisclosure,
  EmptyState,
  InlineNotice,
  PillActionButton,
  PrimaryButton,
  SectionHeader,
  StatusBadge,
  SurfaceCard,
} from "../index";

describe("shared ui primitives", () => {
  it("shows loading copy for PrimaryButton", () => {
    render(
      <PrimaryButton label="Login" loadingLabel="Logging in..." loading onPress={() => undefined} />,
    );

    expect(screen.getByText("Logging in...")).toBeTruthy();
  });

  it("renders the refreshed rounded shell for primary actions and elevated surfaces", () => {
    const { UNSAFE_getByType } = render(
      <AppScreen title="Today">
        <PrimaryButton label="进入门店助理" onPress={() => undefined} />
        <SurfaceCard tone="default" emphasis="elevated">
          <SectionHeader title="店铺概览" subtitle="先看经营状态，再安排今天的处理顺序。" />
        </SurfaceCard>
      </AppScreen>,
    );

    const primaryButton = UNSAFE_getByType(Pressable);
    const buttonStyle = StyleSheet.flatten(primaryButton.props.style({ pressed: false }));
    expect(buttonStyle.backgroundColor).toBe("#3f8f63");
    expect(buttonStyle.borderRadius).toBe(18);
    expect(buttonStyle.minHeight).toBe(52);
  });

  it("renders AppTextField label and error copy", () => {
    render(
      <AppTextField
        label="Email"
        value="owner@example.com"
        onChangeText={() => undefined}
        error="Please enter a valid email"
      />,
    );

    expect(screen.getByText("Email")).toBeTruthy();
    expect(screen.getByText("Please enter a valid email")).toBeTruthy();
    expect(screen.getByLabelText("Email").props.accessibilityState?.invalid).toBe(true);
  });

  it("hides and reveals DebugDisclosure content", () => {
    render(
      <DebugDisclosure title="调试工具">
        <InlineNotice tone="neutral" message="Demo reset lives here" />
      </DebugDisclosure>,
    );

    expect(screen.queryByText("Demo reset lives here")).toBeNull();
    expect(screen.getByText("展开调试信息")).toBeTruthy();

    fireEvent.press(screen.getByRole("button", { name: "调试工具" }));

    expect(screen.getByText("Demo reset lives here")).toBeTruthy();
    expect(screen.getByText("收起调试信息")).toBeTruthy();
  });

  it("renders AppScreen with StatusBadge and EmptyState", () => {
    render(
      <AppScreen title="Today">
        <StatusBadge tone="warning" label="Needs confirmation" />
        <EmptyState title="No data yet" description="Start with voice or photo capture." />
      </AppScreen>,
    );

    expect(screen.getByText("Today")).toBeTruthy();
    expect(screen.getByText("Needs confirmation")).toBeTruthy();
    expect(screen.getByText("No data yet")).toBeTruthy();
    expect(screen.getByText("Start with voice or photo capture.")).toBeTruthy();
  });

  it("renders PillActionButton label", () => {
    render(<PillActionButton label="Voice" onPress={() => undefined} />);

    expect(screen.getByText("Voice")).toBeTruthy();
  });

  it("renders SurfaceCard with SectionHeader content", () => {
    render(
      <SurfaceCard tone="default" emphasis="elevated">
        <SectionHeader title="Overview" subtitle="Daily data" />
      </SurfaceCard>,
    );

    expect(screen.getByText("Overview")).toBeTruthy();
    expect(screen.getByText("Daily data")).toBeTruthy();
  });
});
