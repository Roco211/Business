# Phase 18A Yuanbao Mobile UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Blend a Yuanbao-inspired soft mobile visual language into the existing mobile shell while keeping login reliable, dashboard overview-first, and workbench behavior unchanged.

**Architecture:** Refresh the shared mobile theme and primitives first so the login screen, dashboard, and workbench can inherit one coherent surface language. Then update each target surface with test-first changes, keeping navigation structure, backend contracts, and ledger workflows untouched.

**Tech Stack:** Expo 53, React Native 0.79, React Navigation bottom tabs, Jest, Testing Library

---

## File Structure

- Modify: `apps/mobile/src/shared/ui/tokens.ts`
- Modify: `apps/mobile/src/shared/ui/AppScreen.tsx`
- Modify: `apps/mobile/src/shared/ui/SurfaceCard.tsx`
- Modify: `apps/mobile/src/shared/ui/PrimaryButton.tsx`
- Modify: `apps/mobile/src/shared/ui/PillActionButton.tsx`
- Modify: `apps/mobile/src/shared/ui/AppTextField.tsx`
- Modify: `apps/mobile/src/shared/ui/StatusBadge.tsx`
- Modify: `apps/mobile/src/shared/ui/__tests__/primitives.test.tsx`
- Modify: `apps/mobile/src/app/navigation/RootNavigator.tsx`
- Modify: `apps/mobile/src/app/navigation/RootNavigator.test.tsx`
- Modify: `apps/mobile/src/features/auth/screens/LoginScreen.tsx`
- Modify: `apps/mobile/src/features/auth/screens/LoginScreen.test.tsx`
- Modify: `apps/mobile/src/features/dashboard/components/DashboardSummaryHero.tsx`
- Modify: `apps/mobile/src/features/dashboard/components/DashboardQuickActions.tsx`
- Modify: `apps/mobile/src/features/dashboard/screens/DashboardScreen.tsx`
- Modify: `apps/mobile/src/features/dashboard/screens/DashboardScreen.test.tsx`
- Modify: `apps/mobile/src/features/chat/components/WorkbenchHeader.tsx`
- Modify: `apps/mobile/src/features/chat/components/GuidedEntryDock.tsx`
- Modify: `apps/mobile/src/features/chat/components/ConfirmationCardShell.tsx`
- Modify: `apps/mobile/src/features/chat/components/MessageResultCard.tsx`
- Modify: `apps/mobile/src/features/chat/screens/ChatScreen.tsx`
- Modify: `apps/mobile/src/features/chat/screens/ChatScreen.test.tsx`

---

### Task 1: Refresh Shared Theme And Tab Shell

**Files:**
- Modify: `apps/mobile/src/shared/ui/tokens.ts`
- Modify: `apps/mobile/src/shared/ui/AppScreen.tsx`
- Modify: `apps/mobile/src/shared/ui/SurfaceCard.tsx`
- Modify: `apps/mobile/src/shared/ui/PrimaryButton.tsx`
- Modify: `apps/mobile/src/shared/ui/PillActionButton.tsx`
- Modify: `apps/mobile/src/shared/ui/AppTextField.tsx`
- Modify: `apps/mobile/src/shared/ui/StatusBadge.tsx`
- Modify: `apps/mobile/src/shared/ui/__tests__/primitives.test.tsx`
- Modify: `apps/mobile/src/app/navigation/RootNavigator.tsx`
- Modify: `apps/mobile/src/app/navigation/RootNavigator.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// apps/mobile/src/shared/ui/__tests__/primitives.test.tsx
it("renders the primary button with the refreshed rounded shell", () => {
  render(<PrimaryButton label="进入门店助理" />);

  const button = screen.getByRole("button");
  expect(button.props.style[0]).toEqual(
    expect.objectContaining({
      minHeight: 52,
      borderRadius: 18,
    }),
  );
});
```

```tsx
// apps/mobile/src/app/navigation/RootNavigator.test.tsx
it("keeps the three-tab frontline shell after the visual refresh", async () => {
  setAuthSession({ accessToken: "token", issuedAt: "2026-04-10T08:00:00Z" });

  render(<RootNavigator />);

  expect(await screen.findByText("首页")).toBeTruthy();
  expect(screen.getByText("工作台")).toBeTruthy();
  expect(screen.getByText("台账")).toBeTruthy();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm.cmd test -- src/shared/ui/__tests__/primitives.test.tsx src/app/navigation/RootNavigator.test.tsx --runInBand`

Expected: FAIL because the current primitives still use the older colder button shell and the tests assert the refreshed geometry.

- [ ] **Step 3: Write the minimal implementation**

```ts
// apps/mobile/src/shared/ui/tokens.ts
export const color = {
  bgApp: "#f6f2ea",
  bgSurface: "#fffdf8",
  bgElevated: "#ffffff",
  bgMuted: "#f2ece2",
  bgAccentSoft: "#ebe5ff",
  bgBrandSoft: "#e4f3ea",
  bgInverse: "#2f211c",
  fgPrimary: "#2d211c",
  fgSecondary: "rgba(45, 33, 28, 0.72)",
  fgTertiary: "rgba(45, 33, 28, 0.48)",
  accentPrimary: "#3f8f63",
  accentContrast: "#ffffff",
  statusWarning: "#9f6a1f",
  statusError: "#b54435",
  statusSuccess: "#317e57",
  borderSubtle: "rgba(45, 33, 28, 0.08)",
  focusRing: "rgba(63, 143, 99, 0.18)",
} as const;
```

```tsx
// apps/mobile/src/app/navigation/RootNavigator.tsx
<Tab.Navigator
  screenOptions={{
    headerShown: false,
    tabBarActiveTintColor: color.fgPrimary,
    tabBarInactiveTintColor: color.fgTertiary,
    tabBarLabelStyle: styles.tabBarLabel,
    tabBarStyle: styles.tabBar,
    tabBarItemStyle: styles.tabBarItem,
  }}
>
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm.cmd test -- src/shared/ui/__tests__/primitives.test.tsx src/app/navigation/RootNavigator.test.tsx --runInBand`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/mobile/src/shared/ui/tokens.ts apps/mobile/src/shared/ui/AppScreen.tsx apps/mobile/src/shared/ui/SurfaceCard.tsx apps/mobile/src/shared/ui/PrimaryButton.tsx apps/mobile/src/shared/ui/PillActionButton.tsx apps/mobile/src/shared/ui/AppTextField.tsx apps/mobile/src/shared/ui/StatusBadge.tsx apps/mobile/src/shared/ui/__tests__/primitives.test.tsx apps/mobile/src/app/navigation/RootNavigator.tsx apps/mobile/src/app/navigation/RootNavigator.test.tsx
git commit -m "feat: refresh frontline theme primitives"
```

---

### Task 2: Rebuild The Login Screen Around A Brand-First Mobile Entry

**Files:**
- Modify: `apps/mobile/src/features/auth/screens/LoginScreen.tsx`
- Modify: `apps/mobile/src/features/auth/screens/LoginScreen.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// apps/mobile/src/features/auth/screens/LoginScreen.test.tsx
it("renders the new brand-first mobile entry copy", () => {
  render(<LoginScreen />);

  expect(screen.getByText("门店助理")).toBeTruthy();
  expect(screen.getByText("轻松看店、理货、记账")).toBeTruthy();
  expect(screen.getByText("进入门店助理")).toBeTruthy();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm.cmd test -- src/features/auth/screens/LoginScreen.test.tsx --runInBand`

Expected: FAIL because the current screen still renders the previous engineering-oriented heading and button label.

- [ ] **Step 3: Write the minimal implementation**

```tsx
// apps/mobile/src/features/auth/screens/LoginScreen.tsx
<View style={styles.brandHero}>
  <View style={styles.brandMark}>
    <Text style={styles.brandMarkText}>S</Text>
  </View>
  <Text style={styles.brandName}>门店助理</Text>
  <Text style={styles.brandTagline}>轻松看店、理货、记账</Text>
</View>
<SurfaceCard emphasis="elevated" style={styles.loginCard}>
  <AppTextField label="邮箱" value={email} onChangeText={setEmail} />
  <AppTextField label="密码" value={password} onChangeText={setPassword} secureTextEntry />
  <PrimaryButton
    label="进入门店助理"
    loading={login.isSubmitting}
    loadingLabel="正在进入..."
    onPress={() => void login.submitLogin(email, password)}
  />
</SurfaceCard>
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm.cmd test -- src/features/auth/screens/LoginScreen.test.tsx --runInBand`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/mobile/src/features/auth/screens/LoginScreen.tsx apps/mobile/src/features/auth/screens/LoginScreen.test.tsx
git commit -m "feat: refresh login shell"
```

---

### Task 3: Turn The Dashboard Into A Softer Overview-First Start Screen

**Files:**
- Modify: `apps/mobile/src/features/dashboard/components/DashboardSummaryHero.tsx`
- Modify: `apps/mobile/src/features/dashboard/components/DashboardQuickActions.tsx`
- Modify: `apps/mobile/src/features/dashboard/screens/DashboardScreen.tsx`
- Modify: `apps/mobile/src/features/dashboard/screens/DashboardScreen.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// apps/mobile/src/features/dashboard/screens/DashboardScreen.test.tsx
it("renders the overview-first guidance hierarchy", () => {
  render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

  expect(screen.getByText("今天先看店铺概览")).toBeTruthy();
  expect(screen.getByText("店铺概览")).toBeTruthy();
  expect(screen.getByText("推荐下一步")).toBeTruthy();
  expect(screen.getByText("常用操作")).toBeTruthy();
});
```

```tsx
// apps/mobile/src/features/dashboard/screens/DashboardScreen.test.tsx
it("renders quick actions with helper subtitles", () => {
  render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

  expect(screen.getByText("语音查货")).toBeTruthy();
  expect(screen.getByText("一句话查看库存和缺货风险")).toBeTruthy();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm.cmd test -- src/features/dashboard/screens/DashboardScreen.test.tsx --runInBand`

Expected: FAIL because the current dashboard still uses the older title stack and pill-only quick actions.

- [ ] **Step 3: Write the minimal implementation**

```tsx
// apps/mobile/src/features/dashboard/components/DashboardSummaryHero.tsx
<SurfaceCard emphasis="elevated" style={styles.hero}>
  <Text style={styles.eyebrow}>今天先看店铺概览</Text>
  <Text style={styles.heroTitle}>店铺概览</Text>
  <Text style={styles.heroSubtitle}>先看经营状态，再安排今天的处理顺序。</Text>
  <View style={styles.metrics}>{/* existing four metrics */}</View>
</SurfaceCard>
```

```tsx
// apps/mobile/src/features/dashboard/components/DashboardQuickActions.tsx
const QUICK_ACTIONS = [
  { key: "voice-inventory", label: "语音查货", detail: "一句话查看库存和缺货风险" },
  { key: "photo-stock-in", label: "拍照入库", detail: "对着商品拍照后继续确认" },
  { key: "receipt-ocr", label: "票据识别", detail: "快速整理票据条目和金额" },
  { key: "pending-confirmations", label: "待确认", detail: "集中处理待复核事项" },
] as const;
```

```tsx
// apps/mobile/src/features/dashboard/screens/DashboardScreen.tsx
<SurfaceCard tone="muted" style={styles.guidanceCard}>
  <SectionHeader title="推荐下一步" subtitle={nextActionCopy} />
</SurfaceCard>
<DashboardQuickActions onNavigateToWorkbench={handleNavigateToWorkbench} />
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm.cmd test -- src/features/dashboard/screens/DashboardScreen.test.tsx --runInBand`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/mobile/src/features/dashboard/components/DashboardSummaryHero.tsx apps/mobile/src/features/dashboard/components/DashboardQuickActions.tsx apps/mobile/src/features/dashboard/screens/DashboardScreen.tsx apps/mobile/src/features/dashboard/screens/DashboardScreen.test.tsx
git commit -m "feat: refresh dashboard overview shell"
```

---

### Task 4: Refresh The Workbench Shell Without Changing Its Behavior

**Files:**
- Modify: `apps/mobile/src/features/chat/components/WorkbenchHeader.tsx`
- Modify: `apps/mobile/src/features/chat/components/GuidedEntryDock.tsx`
- Modify: `apps/mobile/src/features/chat/components/ConfirmationCardShell.tsx`
- Modify: `apps/mobile/src/features/chat/components/MessageResultCard.tsx`
- Modify: `apps/mobile/src/features/chat/screens/ChatScreen.tsx`
- Modify: `apps/mobile/src/features/chat/screens/ChatScreen.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// apps/mobile/src/features/chat/screens/ChatScreen.test.tsx
it("renders the softened workbench shell copy", async () => {
  render(<ChatScreen />);

  expect(await screen.findByText("门店助理")).toBeTruthy();
  expect(screen.getByText("常用入口")).toBeTruthy();
  expect(screen.getByText("发消息给门店助理")).toBeTruthy();
});
```

```tsx
// apps/mobile/src/features/chat/screens/ChatScreen.test.tsx
it("keeps confirmation actions visible in the refreshed shell", async () => {
  render(<ChatScreen />);

  expect(await screen.findByText("确认出库")).toBeTruthy();
  expect(screen.getByText("驳回")).toBeTruthy();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm.cmd test -- src/features/chat/screens/ChatScreen.test.tsx --runInBand`

Expected: FAIL because the current workbench still exposes the older "聊天工作台" shell and older composer copy.

- [ ] **Step 3: Write the minimal implementation**

```tsx
// apps/mobile/src/features/chat/components/WorkbenchHeader.tsx
<View style={styles.identityRow}>
  <View>
    <Text style={styles.assistantName}>门店助理</Text>
    <Text style={styles.sessionTitle}>{sessionTitle}</Text>
  </View>
  <StatusBadge tone={getConnectionTone(connectionState)} label={connectionCopy.title} />
</View>
<Text style={styles.hint}>{resolvedHint}</Text>
```

```tsx
// apps/mobile/src/features/chat/components/GuidedEntryDock.tsx
const COPY = {
  title: "常用入口",
  subtitle: "语音、拍照和票据都可以从这里发起。",
  voice: "语音查货",
  photo: "拍照入库",
  receipt: "票据识别",
} as const;
```

```tsx
// apps/mobile/src/features/chat/screens/ChatScreen.tsx
const COPY = {
  workbenchTitle: "门店助理",
  composeTitle: "发消息给门店助理",
  composeSubtitle: "可以直接描述需求，也可以先选上面的常用入口。",
} as const;
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm.cmd test -- src/features/chat/screens/ChatScreen.test.tsx --runInBand`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/mobile/src/features/chat/components/WorkbenchHeader.tsx apps/mobile/src/features/chat/components/GuidedEntryDock.tsx apps/mobile/src/features/chat/components/ConfirmationCardShell.tsx apps/mobile/src/features/chat/components/MessageResultCard.tsx apps/mobile/src/features/chat/screens/ChatScreen.tsx apps/mobile/src/features/chat/screens/ChatScreen.test.tsx
git commit -m "feat: refresh workbench assistant shell"
```

---

### Task 5: Run Full Mobile Verification And Stabilize

**Files:**
- Modify: any touched files from Tasks 1-4 if verification exposes drift

- [ ] **Step 1: Run the targeted refreshed suites**

Run: `npm.cmd test -- src/features/auth/screens/LoginScreen.test.tsx src/features/dashboard/screens/DashboardScreen.test.tsx src/features/chat/screens/ChatScreen.test.tsx src/shared/ui/__tests__/primitives.test.tsx src/app/navigation/RootNavigator.test.tsx --runInBand`

Expected: PASS for all refreshed shell suites.

- [ ] **Step 2: Run the full mobile test suite**

Run: `npm.cmd test -- --runInBand`

Expected: PASS for the full `apps/mobile` Jest suite.

- [ ] **Step 3: Review for spec coverage**

```txt
Confirm visually and in code that:
- login is brand-first but still credential-driven
- dashboard remains overview-first
- workbench remains behaviorally unchanged but visually softened
- ledger was not unintentionally redesigned
```

- [ ] **Step 4: Commit the verification pass**

```bash
git add apps/mobile
git commit -m "test: verify yuanbao-inspired frontline refresh"
```

---

## Self-Review

- Spec coverage check:
  - shared visual language -> Task 1
  - login refresh -> Task 2
  - dashboard overview-first hierarchy -> Task 3
  - workbench shell refresh -> Task 4
  - final verification -> Task 5
- Placeholder scan:
  - no placeholder markers remain
  - each task contains explicit files, commands, and target assertions
- Type consistency:
  - shared file names and screen names match the current codebase
  - action and screen references stay within the existing `首页 / 工作台 / 台账` shell
