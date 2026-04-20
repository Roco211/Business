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

- [x] **Step 1: Write the failing tests**

```tsx
// apps/mobile/src/shared/ui/__tests__/primitives.test.tsx
it("renders the primary button with the refreshed rounded shell", () => {
  render(<PrimaryButton label="鏉╂稑鍙嗛棬搴楀姪鐞? />);

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

  expect(await screen.findByText("棣栭〉")).toBeTruthy();
  expect(screen.getByText("宸ヤ綔鍙?).toBeTruthy();
  expect(screen.getByText("鍙拌处")).toBeTruthy();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm.cmd test -- src/shared/ui/__tests__/primitives.test.tsx src/app/navigation/RootNavigator.test.tsx --runInBand`

Expected: FAIL because the current primitives still use the older colder button shell and the tests assert the refreshed geometry.

- [x] **Step 3: Write the minimal implementation**

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

- [x] **Step 4: Run the tests to verify they pass**

Run: `npm.cmd test -- src/shared/ui/__tests__/primitives.test.tsx src/app/navigation/RootNavigator.test.tsx --runInBand`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add apps/mobile/src/shared/ui/tokens.ts apps/mobile/src/shared/ui/AppScreen.tsx apps/mobile/src/shared/ui/SurfaceCard.tsx apps/mobile/src/shared/ui/PrimaryButton.tsx apps/mobile/src/shared/ui/PillActionButton.tsx apps/mobile/src/shared/ui/AppTextField.tsx apps/mobile/src/shared/ui/StatusBadge.tsx apps/mobile/src/shared/ui/__tests__/primitives.test.tsx apps/mobile/src/app/navigation/RootNavigator.tsx apps/mobile/src/app/navigation/RootNavigator.test.tsx
git commit -m "feat: refresh frontline theme primitives"
```

---

### Task 2: Rebuild The Login Screen Around A Brand-First Mobile Entry

**Files:**
- Modify: `apps/mobile/src/features/auth/screens/LoginScreen.tsx`
- Modify: `apps/mobile/src/features/auth/screens/LoginScreen.test.tsx`

- [x] **Step 1: Write the failing tests**

```tsx
// apps/mobile/src/features/auth/screens/LoginScreen.test.tsx
it("renders the new brand-first mobile entry copy", () => {
  render(<LoginScreen />);

  expect(screen.getByText("闂ㄥ簵鍔╃悊")).toBeTruthy();
  expect(screen.getByText("鏉炵粯婢楅惇瀣暗閵嗕胶鎮婄拹褋鈧浇顔囩拹?)).toBeTruthy();
  expect(screen.getByText("鏉╂稑鍙嗛棬搴楀姪鐞?)).toBeTruthy();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm.cmd test -- src/features/auth/screens/LoginScreen.test.tsx --runInBand`

Expected: FAIL because the current screen still renders the previous engineering-oriented heading and button label.

- [x] **Step 3: Write the minimal implementation**

```tsx
// apps/mobile/src/features/auth/screens/LoginScreen.tsx
<View style={styles.brandHero}>
  <View style={styles.brandMark}>
    <Text style={styles.brandMarkText}>S</Text>
  </View>
  <Text style={styles.brandName}>闂ㄥ簵鍔╃悊</Text>
  <Text style={styles.brandTagline}>鏉炵粯婢楅惇瀣暗閵嗕胶鎮婄拹褋鈧浇顔囩拹?/Text>
</View>
<SurfaceCard emphasis="elevated" style={styles.loginCard}>
  <AppTextField label="闁喚顔? value={email} onChangeText={setEmail} />
  <AppTextField label="鐎靛棛鐖? value={password} onChangeText={setPassword} secureTextEntry />
  <PrimaryButton
    label="鏉╂稑鍙嗛棬搴楀姪鐞?
    loading={login.isSubmitting}
    loadingLabel="濮濓絽婀潻娑樺弳..."
    onPress={() => void login.submitLogin(email, password)}
  />
</SurfaceCard>
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `npm.cmd test -- src/features/auth/screens/LoginScreen.test.tsx --runInBand`

Expected: PASS.

- [x] **Step 5: Commit**

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

- [x] **Step 1: Write the failing tests**

```tsx
// apps/mobile/src/features/dashboard/screens/DashboardScreen.test.tsx
it("renders the overview-first guidance hierarchy", () => {
  render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

  expect(screen.getByText("娴犲﹤銇夐崗鍫㈡箙鎼存鎽靛鍌濐潔")).toBeTruthy();
  expect(screen.getByText("鎼存鎽靛鍌濐潔")).toBeTruthy();
  expect(screen.getByText("閹恒劏宕樻稉瀣╃濮?)).toBeTruthy();
  expect(screen.getByText("鐢摜鏁ら幙宥勭稊")).toBeTruthy();
});
```

```tsx
// apps/mobile/src/features/dashboard/screens/DashboardScreen.test.tsx
it("renders quick actions with helper subtitles", () => {
  render(<DashboardScreen navigation={{ navigate: mockNavigate } as never} />);

  expect(screen.getByText("璇煶鏌ヨ揣")).toBeTruthy();
  expect(screen.getByText("娑撯偓閸欍儴鐦介弻銉ф箙鎼存挸鐡ㄩ崪宀€宸辩拹褔顥撻梽?)).toBeTruthy();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm.cmd test -- src/features/dashboard/screens/DashboardScreen.test.tsx --runInBand`

Expected: FAIL because the current dashboard still uses the older title stack and pill-only quick actions.

- [x] **Step 3: Write the minimal implementation**

```tsx
// apps/mobile/src/features/dashboard/components/DashboardSummaryHero.tsx
<SurfaceCard emphasis="elevated" style={styles.hero}>
  <Text style={styles.eyebrow}>娴犲﹤銇夐崗鍫㈡箙鎼存鎽靛鍌濐潔</Text>
  <Text style={styles.heroTitle}>鎼存鎽靛鍌濐潔</Text>
  <Text style={styles.heroSubtitle}>閸忓牏婀呯紒蹇氭儉閻樿埖鈧緤绱濋崘宥呯暔閹烘帊绮栨径鈺冩畱婢跺嫮鎮婃い鍝勭碍閵?/Text>
  <View style={styles.metrics}>{/* existing four metrics */}</View>
</SurfaceCard>
```

```tsx
// apps/mobile/src/features/dashboard/components/DashboardQuickActions.tsx
const QUICK_ACTIONS = [
  { key: "voice-inventory", label: "璇煶鏌ヨ揣", detail: "娑撯偓閸欍儴鐦介弻銉ф箙鎼存挸鐡ㄩ崪宀€宸辩拹褔顥撻梽? },
  { key: "photo-stock-in", label: "拍照入库", detail: "鐎靛湱娼冮崯鍡楁惂閹峰秶鍙庨崥搴ｆ埛缂侇厾鈥樼拋? },
  { key: "receipt-ocr", label: "绁ㄦ嵁璇嗗埆", detail: "韫囶偊鈧喐鏆ｉ悶鍡欍偍閹诡喗娼惄顔兼嫲闁叉垿顤? },
  { key: "pending-confirmations", label: "瀵板懐鈥樼拋?, detail: "闂嗗棔鑵戞径鍕倞瀵板懎顦查弽闀愮皑妞? },
] as const;
```

```tsx
// apps/mobile/src/features/dashboard/screens/DashboardScreen.tsx
<SurfaceCard tone="muted" style={styles.guidanceCard}>
  <SectionHeader title="閹恒劏宕樻稉瀣╃濮? subtitle={nextActionCopy} />
</SurfaceCard>
<DashboardQuickActions onNavigateToWorkbench={handleNavigateToWorkbench} />
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `npm.cmd test -- src/features/dashboard/screens/DashboardScreen.test.tsx --runInBand`

Expected: PASS.

- [x] **Step 5: Commit**

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

- [x] **Step 1: Write the failing tests**

```tsx
// apps/mobile/src/features/chat/screens/ChatScreen.test.tsx
it("renders the softened workbench shell copy", async () => {
  render(<ChatScreen />);

  expect(await screen.findByText("闂ㄥ簵鍔╃悊")).toBeTruthy();
  expect(screen.getByText("常用鍏ュ彛")).toBeTruthy();
  expect(screen.getByText("閸欐垶绉烽幁顖滅舶闂ㄥ簵鍔╃悊")).toBeTruthy();
});
```

```tsx
// apps/mobile/src/features/chat/screens/ChatScreen.test.tsx
it("keeps confirmation actions visible in the refreshed shell", async () => {
  render(<ChatScreen />);

  expect(await screen.findByText("确认鍑哄簱")).toBeTruthy();
  expect(screen.getByText("椹冲洖")).toBeTruthy();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm.cmd test -- src/features/chat/screens/ChatScreen.test.tsx --runInBand`

Expected: FAIL because the current workbench still exposes the older "鑱婂ぉ宸ヤ綔鍙?shell and older composer copy.

- [x] **Step 3: Write the minimal implementation**

```tsx
// apps/mobile/src/features/chat/components/WorkbenchHeader.tsx
<View style={styles.identityRow}>
  <View>
    <Text style={styles.assistantName}>闂ㄥ簵鍔╃悊</Text>
    <Text style={styles.sessionTitle}>{sessionTitle}</Text>
  </View>
  <StatusBadge tone={getConnectionTone(connectionState)} label={connectionCopy.title} />
</View>
<Text style={styles.hint}>{resolvedHint}</Text>
```

```tsx
// apps/mobile/src/features/chat/components/GuidedEntryDock.tsx
const COPY = {
  title: "常用鍏ュ彛",
  subtitle: "鐠囶參鐓堕妴浣瑰閻撗冩嫲缁併劍宓侀柈钘夊讲娴犮儰绮犳潻娆撳櫡閸欐垼鎹ｉ妴?,
  voice: "璇煶鏌ヨ揣",
  photo: "拍照入库",
  receipt: "绁ㄦ嵁璇嗗埆",
} as const;
```

```tsx
// apps/mobile/src/features/chat/screens/ChatScreen.tsx
const COPY = {
  workbenchTitle: "闂ㄥ簵鍔╃悊",
  composeTitle: "閸欐垶绉烽幁顖滅舶闂ㄥ簵鍔╃悊",
  composeSubtitle: "閸欘垯浜掗惄瀛樺复閹诲繗鍫棁鈧Ч鍌︾礉娑旂喎褰叉禒銉ュ帥闁绗傞棃銏㈡畱常用鍏ュ彛閵?,
} as const;
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `npm.cmd test -- src/features/chat/screens/ChatScreen.test.tsx --runInBand`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add apps/mobile/src/features/chat/components/WorkbenchHeader.tsx apps/mobile/src/features/chat/components/GuidedEntryDock.tsx apps/mobile/src/features/chat/components/ConfirmationCardShell.tsx apps/mobile/src/features/chat/components/MessageResultCard.tsx apps/mobile/src/features/chat/screens/ChatScreen.tsx apps/mobile/src/features/chat/screens/ChatScreen.test.tsx
git commit -m "feat: refresh workbench assistant shell"
```

---

### Task 5: Run Full Mobile Verification And Stabilize

**Files:**
- Modify: any touched files from Tasks 1-4 if verification exposes drift

- [x] **Step 1: Run the targeted refreshed suites**

Run: `npm.cmd test -- src/features/auth/screens/LoginScreen.test.tsx src/features/dashboard/screens/DashboardScreen.test.tsx src/features/chat/screens/ChatScreen.test.tsx src/shared/ui/__tests__/primitives.test.tsx src/app/navigation/RootNavigator.test.tsx --runInBand`

Expected: PASS for all refreshed shell suites.

- [x] **Step 2: Run the full mobile test suite**

Run: `npm.cmd test -- --runInBand`

Expected: PASS for the full `apps/mobile` Jest suite.

- [x] **Step 3: Review for spec coverage**

```txt
Confirm visually and in code that:
- login is brand-first but still credential-driven
- dashboard remains overview-first
- workbench remains behaviorally unchanged but visually softened
- ledger was not unintentionally redesigned
```

- [x] **Step 4: Commit the verification pass**

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
  - action and screen references stay within the existing `棣栭〉 / 宸ヤ綔鍙?/ 鍙拌处` shell
