# Phase 17B Mobile Usability Rescue And Trial-Ready Frontline Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Android Expo app readable, connectable, and trustworthy enough for guided trial rehearsal before integrating `coding plan` or real multimodal providers.

**Architecture:** Keep the existing Expo shell, auth/session bootstrap flow, bottom-tab navigation, and backend contracts, but add a stricter frontline presentation layer for copy, connectivity, and non-demo default paths. Implement the rescue in layers: shared copy/status normalization, Expo/device API resolution, login/dashboard/workbench/ledger hardening, then backend user-facing runtime copy cleanup.

**Tech Stack:** Expo 53, React Native 0.79, React Navigation, Jest + Testing Library, FastAPI, pytest

---

## File Structure

- Create: `apps/mobile/src/shared/copy/frontlineStatus.ts`
- Create: `apps/mobile/src/shared/copy/__tests__/frontlineStatus.test.ts`
- Create: `apps/mobile/src/shared/api/resolveApiBaseUrl.ts`
- Create: `apps/mobile/src/shared/api/__tests__/resolveApiBaseUrl.test.ts`
- Create: `apps/mobile/src/shared/session/getWorkbenchConnectionCopy.ts`
- Create: `apps/mobile/src/features/chat/utils/presentRuntimeMessageText.ts`
- Create: `apps/mobile/src/features/chat/utils/presentRuntimeMessageText.test.ts`
- Modify: `apps/mobile/src/shared/copy/getFriendlyStatusMessage.ts`
- Modify: `apps/mobile/src/shared/api/client.ts`
- Modify: `apps/mobile/src/shared/session/useBootstrapSession.ts`
- Modify: `apps/mobile/src/shared/session/SessionStreamProvider.tsx`
- Modify: `apps/mobile/src/features/auth/screens/LoginScreen.tsx`
- Modify: `apps/mobile/src/features/auth/screens/LoginScreen.test.tsx`
- Modify: `apps/mobile/src/features/dashboard/screens/DashboardScreen.tsx`
- Modify: `apps/mobile/src/features/dashboard/screens/DashboardScreen.test.tsx`
- Modify: `apps/mobile/src/features/chat/components/WorkbenchHeader.tsx`
- Modify: `apps/mobile/src/features/chat/components/GuidedEntryDock.tsx`
- Modify: `apps/mobile/src/features/chat/components/MockMediaEntryPanel.tsx`
- Modify: `apps/mobile/src/features/chat/screens/ChatScreen.tsx`
- Modify: `apps/mobile/src/features/chat/screens/ChatScreen.test.tsx`
- Modify: `apps/mobile/src/features/ledger/screens/LedgerScreen.tsx`
- Modify: `apps/mobile/src/features/ledger/screens/LedgerScreen.test.tsx`
- Modify: `apps/mobile/src/shared/ui/DebugDisclosure.tsx`
- Modify: `backend/app/runtime/summarizer.py`
- Modify: `backend/app/runtime/processor.py`
- Modify: `backend/app/api/routes/confirmations.py`
- Modify: `backend/app/services/approved_stock_in_commits.py`
- Modify: `backend/app/services/approved_stock_out_commits.py`
- Modify: `backend/app/services/approved_receipt_stock_in_commits.py`
- Modify: `backend/tests/test_runtime_processor.py`
- Modify: `backend/tests/test_inventory_commit_service.py`
- Create: `project_docs/mobile-trial-shell-checklist.md`

---

### Task 1: Shared Frontline Copy And Status Foundation

**Files:**
- Create: `apps/mobile/src/shared/copy/frontlineStatus.ts`
- Create: `apps/mobile/src/shared/copy/__tests__/frontlineStatus.test.ts`
- Modify: `apps/mobile/src/shared/copy/getFriendlyStatusMessage.ts`
- Modify: `apps/mobile/__tests__/getFriendlyStatusMessage.test.ts`

- [x] **Step 1: Write the failing tests**

```ts
// apps/mobile/src/shared/copy/__tests__/frontlineStatus.test.ts
import { FRONTLINE_STATUS_COPY, normalizeRuntimeMessage } from "../frontlineStatus";

it("maps leaked mock runtime copy into frontline wording", () => {
  expect(
    normalizeRuntimeMessage(
      "Mock runtime: stock query accepted. Fixture inventory shows low stock for the requested item.",
    ),
  ).toBe("\u5df2\u6536\u5230\u67e5\u8d27\u8bf7\u6c42\uff0c\u8bf7\u67e5\u770b\u5f53\u524d\u5e93\u5b58\u7ed3\u679c\u3002");
});

it("keeps stable network fallback copy", () => {
  expect(FRONTLINE_STATUS_COPY.networkUnavailable).toBe(
    "\u5f53\u524d\u65e0\u6cd5\u8fde\u63a5\u95e8\u5e97\u670d\u52a1\uff0c\u8bf7\u68c0\u67e5\u7f51\u7edc\u540e\u91cd\u8bd5\u3002",
  );
});
```

```ts
// apps/mobile/__tests__/getFriendlyStatusMessage.test.ts
import { getFriendlyStatusMessage } from "../src/shared/copy/getFriendlyStatusMessage";

it("normalizes network failures and leaked mock copy", () => {
  expect(
    getFriendlyStatusMessage(
      "Cannot reach API at http://192.168.1.4:8001 (Network request failed)",
      "\u8bf7\u7a0d\u540e\u518d\u8bd5\u3002",
    ),
  ).toBe("\u5f53\u524d\u65e0\u6cd5\u8fde\u63a5\u95e8\u5e97\u670d\u52a1\uff0c\u8bf7\u68c0\u67e5\u7f51\u7edc\u540e\u91cd\u8bd5\u3002");

  expect(
    getFriendlyStatusMessage(
      "Mock runtime could not process this task: Image recognition failed",
      "\u8bf7\u7a0d\u540e\u518d\u8bd5\u3002",
    ),
  ).toBe("\u5f53\u524d\u4efb\u52a1\u6682\u65f6\u65e0\u6cd5\u5b8c\u6210\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002");
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm.cmd test -- src/shared/copy/__tests__/frontlineStatus.test.ts __tests__/getFriendlyStatusMessage.test.ts --runInBand`

Expected: FAIL because `frontlineStatus.ts` does not exist and the current helper still returns mojibake/raw mock wording.

- [x] **Step 3: Write the minimal implementation**

```ts
// apps/mobile/src/shared/copy/frontlineStatus.ts
export const FRONTLINE_STATUS_COPY = {
  networkUnavailable:
    "\u5f53\u524d\u65e0\u6cd5\u8fde\u63a5\u95e8\u5e97\u670d\u52a1\uff0c\u8bf7\u68c0\u67e5\u7f51\u7edc\u540e\u91cd\u8bd5\u3002",
  loginUnavailable:
    "\u5f53\u524d\u65e0\u6cd5\u5b8c\u6210\u767b\u5f55\uff0c\u8bf7\u68c0\u67e5\u8d26\u53f7\u3001\u7f51\u7edc\u6216\u670d\u52a1\u72b6\u6001\u540e\u91cd\u8bd5\u3002",
  workbenchUnavailable:
    "\u5de5\u4f5c\u53f0\u6682\u65f6\u4e0d\u53ef\u7528\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5\u3002",
  taskFailed:
    "\u5f53\u524d\u4efb\u52a1\u6682\u65f6\u65e0\u6cd5\u5b8c\u6210\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002",
  realtimeDegraded:
    "\u5b9e\u65f6\u66f4\u65b0\u6682\u65f6\u4e0d\u53ef\u7528\uff0c\u5b8c\u6210\u64cd\u4f5c\u540e\u4ecd\u53ef\u624b\u52a8\u5237\u65b0\u3002",
} as const;

export function normalizeRuntimeMessage(message: string): string {
  const trimmed = message.trim();
  if (!trimmed) return trimmed;
  if (/could not process this task/i.test(trimmed)) return FRONTLINE_STATUS_COPY.taskFailed;
  if (/stock query accepted/i.test(trimmed)) {
    return "\u5df2\u6536\u5230\u67e5\u8d27\u8bf7\u6c42\uff0c\u8bf7\u67e5\u770b\u5f53\u524d\u5e93\u5b58\u7ed3\u679c\u3002";
  }
  if (/receipt OCR completed/i.test(trimmed)) {
    return "\u7968\u636e\u8bc6\u522b\u5df2\u5b8c\u6210\uff0c\u8bf7\u6838\u5bf9\u91d1\u989d\u4e0e\u6761\u76ee\u3002";
  }
  if (/stock-in intent accepted/i.test(trimmed)) {
    return "\u5df2\u6536\u5230\u5165\u5e93\u8bf7\u6c42\uff0c\u8bf7\u7ee7\u7eed\u786e\u8ba4\u540e\u63d0\u4ea4\u3002";
  }
  return trimmed.replace(/^Mock runtime:\s*/i, "");
}
```

```ts
// apps/mobile/src/shared/copy/getFriendlyStatusMessage.ts
import { FRONTLINE_STATUS_COPY, normalizeRuntimeMessage } from "./frontlineStatus";

const CHINESE_CHARACTER_PATTERN = /[\u3400-\u9fff]/;
const NETWORK_ERROR_PATTERN =
  /(network request failed|failed to fetch|fetch failed|cannot reach api|econnrefused|timeout|timed out)/i;

export function getFriendlyStatusMessage(message: string | null | undefined, fallbackMessage: string) {
  const trimmedMessage = message?.trim();
  if (!trimmedMessage) return fallbackMessage;
  if (NETWORK_ERROR_PATTERN.test(trimmedMessage)) return FRONTLINE_STATUS_COPY.networkUnavailable;
  const normalizedMessage = normalizeRuntimeMessage(trimmedMessage);
  if (CHINESE_CHARACTER_PATTERN.test(normalizedMessage)) return normalizedMessage;
  return normalizedMessage || fallbackMessage;
}
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `npm.cmd test -- src/shared/copy/__tests__/frontlineStatus.test.ts __tests__/getFriendlyStatusMessage.test.ts --runInBand`

Expected: PASS for both suites.

- [x] **Step 5: Commit**

```bash
git add apps/mobile/src/shared/copy/frontlineStatus.ts apps/mobile/src/shared/copy/__tests__/frontlineStatus.test.ts apps/mobile/src/shared/copy/getFriendlyStatusMessage.ts apps/mobile/__tests__/getFriendlyStatusMessage.test.ts
git commit -m "feat: add frontline status copy foundation"
```

---

### Task 2: API Base URL Inference And Runtime Connectivity Baseline

**Files:**
- Create: `apps/mobile/src/shared/api/resolveApiBaseUrl.ts`
- Create: `apps/mobile/src/shared/api/__tests__/resolveApiBaseUrl.test.ts`
- Create: `apps/mobile/src/shared/session/getWorkbenchConnectionCopy.ts`
- Modify: `apps/mobile/src/shared/api/client.ts`
- Modify: `apps/mobile/src/shared/session/useBootstrapSession.ts`
- Modify: `apps/mobile/src/shared/session/SessionStreamProvider.tsx`
- Modify: `apps/mobile/src/features/chat/components/WorkbenchHeader.tsx`
- Modify: `apps/mobile/src/features/chat/screens/ChatScreen.test.tsx`

- [x] **Step 1: Write the failing tests**

```ts
// apps/mobile/src/shared/api/__tests__/resolveApiBaseUrl.test.ts
import { inferDevServerHost, resolveApiBaseUrl } from "../resolveApiBaseUrl";

it("infers the Metro host for Expo Go on a real Android device", () => {
  expect(
    resolveApiBaseUrl({
      configuredBaseUrl: "",
      platform: "android",
      scriptURL: "http://192.168.1.4:8081/node_modules/expo/AppEntry.bundle?platform=android",
    }),
  ).toBe("http://192.168.1.4:8001");
});

it("falls back to Android emulator localhost only when no host is inferable", () => {
  expect(resolveApiBaseUrl({ configuredBaseUrl: "", platform: "android", scriptURL: null })).toBe(
    "http://10.0.2.2:8001",
  );
  expect(inferDevServerHost("http://192.168.1.4:8081/index.bundle?platform=android")).toBe(
    "192.168.1.4",
  );
});
```

```ts
// apps/mobile/src/features/chat/screens/ChatScreen.test.tsx
it("shows bootstrap-specific recovery copy when session bootstrap fails", async () => {
  mockedUseSessionStream.mockReturnValue({
    sessionId: "sess_1",
    sessionTitle: "Store shift session",
    connectionState: "error",
    bootstrapError: "Cannot reach API at http://192.168.1.4:8001 (Network request failed)",
    lastEvent: null,
    recentEvents: [],
    dataResetVersion: 0,
    notifyDemoDataReset: jest.fn(),
  });

  render(<ChatScreen />);

  expect(await screen.findByText("\u5de5\u4f5c\u53f0\u6682\u65f6\u4e0d\u53ef\u7528")).toBeTruthy();
  expect(
    screen.getByText("\u5f53\u524d\u65e0\u6cd5\u8fde\u63a5\u95e8\u5e97\u670d\u52a1\uff0c\u8bf7\u68c0\u67e5\u7f51\u7edc\u540e\u91cd\u8bd5\u3002"),
  ).toBeTruthy();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm.cmd test -- src/shared/api/__tests__/resolveApiBaseUrl.test.ts src/features/chat/screens/ChatScreen.test.tsx --runInBand`

Expected: FAIL because `resolveApiBaseUrl.ts` does not exist and the workbench state copy still relies on inline mojibake.

- [x] **Step 3: Write the minimal implementation**

```ts
// apps/mobile/src/shared/api/resolveApiBaseUrl.ts
type ResolveApiBaseUrlInput = {
  configuredBaseUrl: string | null | undefined;
  platform: "android" | "ios";
  scriptURL: string | null | undefined;
};

export function inferDevServerHost(scriptURL: string | null | undefined): string | null {
  if (!scriptURL) return null;
  try {
    return new URL(scriptURL).hostname || null;
  } catch {
    return null;
  }
}

export function resolveApiBaseUrl(input: ResolveApiBaseUrlInput): string {
  const configured = input.configuredBaseUrl?.trim();
  if (configured) return configured.replace(/\/+$/, "");
  const inferredHost = inferDevServerHost(input.scriptURL);
  if (inferredHost) return `http://${inferredHost}:8001`;
  return input.platform === "android" ? "http://10.0.2.2:8001" : "http://127.0.0.1:8001";
}
```

```ts
// apps/mobile/src/shared/api/client.ts
import { NativeModules, Platform } from "react-native";
import { resolveApiBaseUrl } from "./resolveApiBaseUrl";

function getScriptURL(): string | null {
  return typeof NativeModules.SourceCode?.scriptURL === "string"
    ? NativeModules.SourceCode.scriptURL
    : null;
}

export function getApiBaseUrl(): string {
  return resolveApiBaseUrl({
    configuredBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL,
    platform: Platform.OS === "android" ? "android" : "ios",
    scriptURL: getScriptURL(),
  });
}
```

```ts
// apps/mobile/src/shared/session/getWorkbenchConnectionCopy.ts
import { FRONTLINE_STATUS_COPY } from "../copy/frontlineStatus";

export function getWorkbenchConnectionCopy(input: {
  bootstrapError: string | null;
  connectionState: "idle" | "bootstrapping" | "connecting" | "connected" | "disconnected" | "error";
}) {
  if (input.bootstrapError) return { title: "\u5de5\u4f5c\u53f0\u6682\u65f6\u4e0d\u53ef\u7528", hint: FRONTLINE_STATUS_COPY.networkUnavailable };
  if (input.connectionState === "connected") return { title: "\u5df2\u8fde\u63a5", hint: "\u5b9e\u65f6\u66f4\u65b0\u6b63\u5e38\u3002" };
  if (input.connectionState === "connecting" || input.connectionState === "bootstrapping") return { title: "\u6b63\u5728\u8fde\u63a5", hint: "\u6b63\u5728\u540c\u6b65\u4f1a\u8bdd\u4e0e\u5b9e\u65f6\u66f4\u65b0\u3002" };
  if (input.connectionState === "disconnected" || input.connectionState === "error") return { title: "\u8fde\u63a5\u53d7\u9650", hint: FRONTLINE_STATUS_COPY.realtimeDegraded };
  return { title: "\u7b49\u5f85\u8fde\u63a5", hint: "\u8bf7\u7a0d\u5019\uff0c\u5de5\u4f5c\u53f0\u6b63\u5728\u51c6\u5907\u4e2d\u3002" };
}
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `npm.cmd test -- src/shared/api/__tests__/resolveApiBaseUrl.test.ts src/features/chat/screens/ChatScreen.test.tsx --runInBand`

Expected: PASS, with host inference and bootstrap-specific workbench copy covered.

- [x] **Step 5: Commit**

```bash
git add apps/mobile/src/shared/api/resolveApiBaseUrl.ts apps/mobile/src/shared/api/__tests__/resolveApiBaseUrl.test.ts apps/mobile/src/shared/api/client.ts apps/mobile/src/shared/session/getWorkbenchConnectionCopy.ts apps/mobile/src/shared/session/useBootstrapSession.ts apps/mobile/src/shared/session/SessionStreamProvider.tsx apps/mobile/src/features/chat/components/WorkbenchHeader.tsx apps/mobile/src/features/chat/screens/ChatScreen.test.tsx
git commit -m "feat: add mobile connectivity baseline"
```

---

### Task 3: Login And Dashboard Trial-Shell Rescue

**Files:**
- Modify: `apps/mobile/src/features/auth/screens/LoginScreen.tsx`
- Modify: `apps/mobile/src/features/auth/screens/LoginScreen.test.tsx`
- Modify: `apps/mobile/src/features/dashboard/screens/DashboardScreen.tsx`
- Modify: `apps/mobile/src/features/dashboard/screens/DashboardScreen.test.tsx`

- [x] **Step 1: Write the failing tests**

```ts
// apps/mobile/src/features/auth/screens/LoginScreen.test.tsx
it("shows readable hero copy and keeps environment details secondary", () => {
  render(<LoginScreen />);
  expect(screen.getByText("\u95e8\u5e97\u5e93\u5b58\u52a9\u624b")).toBeTruthy();
  expect(screen.getByText("\u8fde\u63a5\u95e8\u5e97\u670d\u52a1\u540e\u5373\u53ef\u5f00\u59cb\u4f7f\u7528\u5de5\u4f5c\u53f0\u3002")).toBeTruthy();
  expect(screen.queryByText("http://10.0.2.2:8001")).toBeNull();
});

// apps/mobile/src/features/dashboard/screens/DashboardScreen.test.tsx
it("shows health wording before debug tools", () => {
  render(<DashboardScreen navigation={{ navigate: jest.fn() } as never} />);
  expect(screen.getByText("\u4eca\u65e5\u95e8\u5e97")).toBeTruthy();
  expect(screen.getByText("\u5f53\u524d\u5df2\u8fde\u63a5")).toBeTruthy();
  expect(screen.getByLabelText("\u8c03\u8bd5\u5de5\u5177")).toBeTruthy();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm.cmd test -- src/features/auth/screens/LoginScreen.test.tsx src/features/dashboard/screens/DashboardScreen.test.tsx --runInBand`

Expected: FAIL because the current screens still render mojibake copy and do not foreground app health/next action wording.

- [x] **Step 3: Write the minimal implementation**

```tsx
// apps/mobile/src/features/auth/screens/LoginScreen.tsx
const COPY = {
  eyebrow: "\u95e8\u5e97\u8bd5\u70b9",
  title: "\u95e8\u5e97\u5e93\u5b58\u52a9\u624b",
  subtitle: "\u8bed\u97f3\u3001\u62cd\u7167\u3001\u7968\u636e\u7edf\u4e00\u5165\u8d26",
  helper: "\u8fde\u63a5\u95e8\u5e97\u670d\u52a1\u540e\u5373\u53ef\u5f00\u59cb\u4f7f\u7528\u5de5\u4f5c\u53f0\u3002",
};
```

```tsx
// apps/mobile/src/features/dashboard/screens/DashboardScreen.tsx
<AppScreen title="\u4eca\u65e5\u95e8\u5e97" subtitle="\u5148\u770b\u98ce\u9669\uff0c\u518d\u5b89\u6392\u4eca\u5929\u7684\u5904\u7406\u52a8\u4f5c\u3002">
  <InlineNotice
    tone="success"
    title="\u5f53\u524d\u5df2\u8fde\u63a5"
    message="\u4f18\u5148\u5904\u7406\u5f85\u786e\u8ba4\u548c\u4f4e\u5e93\u5b58\u4e8b\u9879\u3002"
  />
  <DashboardSummaryHero summary={summary.data} />
  <DashboardQuickActions onNavigateToWorkbench={handleNavigateToWorkbench} />
  <DebugDisclosure title="\u8c03\u8bd5\u5de5\u5177">
    <View style={styles.debugPanel}>
      <PrimaryButton
        label="\u91cd\u7f6e\u6f14\u793a\u6570\u636e"
        onPress={() => {
          void handleDemoReset();
        }}
      />
    </View>
  </DebugDisclosure>
</AppScreen>
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `npm.cmd test -- src/features/auth/screens/LoginScreen.test.tsx src/features/dashboard/screens/DashboardScreen.test.tsx --runInBand`

Expected: PASS with corrected copy and dashboard health emphasis.

- [x] **Step 5: Commit**

```bash
git add apps/mobile/src/features/auth/screens/LoginScreen.tsx apps/mobile/src/features/auth/screens/LoginScreen.test.tsx apps/mobile/src/features/dashboard/screens/DashboardScreen.tsx apps/mobile/src/features/dashboard/screens/DashboardScreen.test.tsx
git commit -m "feat: rescue login and dashboard trial shell"
```

---

### Task 4: Workbench De-Demoization And Frontend Runtime Message Presentation

**Files:**
- Create: `apps/mobile/src/features/chat/utils/presentRuntimeMessageText.ts`
- Create: `apps/mobile/src/features/chat/utils/presentRuntimeMessageText.test.ts`
- Modify: `apps/mobile/src/features/chat/components/GuidedEntryDock.tsx`
- Modify: `apps/mobile/src/features/chat/components/MockMediaEntryPanel.tsx`
- Modify: `apps/mobile/src/features/chat/screens/ChatScreen.tsx`
- Modify: `apps/mobile/src/features/chat/screens/ChatScreen.test.tsx`

- [x] **Step 1: Write the failing tests**

```ts
// apps/mobile/src/features/chat/utils/presentRuntimeMessageText.test.ts
import { presentRuntimeMessageText } from "./presentRuntimeMessageText";

it("removes mock runtime prefixes from result copy", () => {
  expect(
    presentRuntimeMessageText(
      "Mock runtime: stock query accepted. Fixture inventory shows low stock for the requested item.",
    ),
  ).toBe("\u5df2\u6536\u5230\u67e5\u8d27\u8bf7\u6c42\uff0c\u8bf7\u67e5\u770b\u5f53\u524d\u5e93\u5b58\u7ed3\u679c\u3002");
});
```

```ts
// apps/mobile/src/features/chat/screens/ChatScreen.test.tsx
it("uses business-language entry actions instead of demo labels in the default path", async () => {
  render(<ChatScreen />);
  expect(await screen.findByText("\u8bed\u97f3\u67e5\u8d27")).toBeTruthy();
  expect(screen.getByText("\u62cd\u7167\u5165\u5e93")).toBeTruthy();
  expect(screen.getByText("\u7968\u636e\u8bc6\u522b")).toBeTruthy();
  expect(screen.queryByText("Voice Query Demo")).toBeNull();
});

it("keeps legacy demo actions behind an explicit debug section", async () => {
  render(<ChatScreen />);
  fireEvent.press(screen.getByLabelText("\u8c03\u8bd5\u5de5\u5177"));
  expect(await screen.findByText("\u8bed\u97f3\u67e5\u8d27\u8c03\u8bd5")).toBeTruthy();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm.cmd test -- src/features/chat/utils/presentRuntimeMessageText.test.ts src/features/chat/screens/ChatScreen.test.tsx --runInBand`

Expected: FAIL because the helper does not exist and the default workbench dock still uses demo-oriented labels.

- [x] **Step 3: Write the minimal implementation**

```ts
// apps/mobile/src/features/chat/utils/presentRuntimeMessageText.ts
import { normalizeRuntimeMessage } from "../../../shared/copy/frontlineStatus";

export function presentRuntimeMessageText(text: string) {
  return normalizeRuntimeMessage(text);
}
```

```tsx
// apps/mobile/src/features/chat/components/GuidedEntryDock.tsx
const COPY = {
  title: "\u5feb\u901f\u53d1\u8d77",
  subtitle: "\u9009\u62e9\u6700\u9002\u5408\u5f53\u524d\u4efb\u52a1\u7684\u8f93\u5165\u65b9\u5f0f\u3002",
  errorTitle: "\u63d0\u4ea4\u5931\u8d25",
  voice: "\u8bed\u97f3\u67e5\u8d27",
  photo: "\u62cd\u7167\u5165\u5e93",
  receipt: "\u7968\u636e\u8bc6\u522b",
} as const;
```

```tsx
// apps/mobile/src/features/chat/components/MockMediaEntryPanel.tsx
<SectionHeader
  title="\u8c03\u8bd5\u5165\u53e3"
  subtitle="\u4ec5\u4f9b\u5f00\u53d1\u9a8c\u8bc1\uff0c\u4e0d\u5c5e\u4e8e\u5e97\u5458\u9ed8\u8ba4\u6d41\u7a0b\u3002"
/>
<PrimaryButton
  label="\u8bed\u97f3\u67e5\u8d27\u8c03\u8bd5"
  onPress={() => {
    void handleVoiceSubmit("query");
  }}
  disabled={isSubmitting}
/>
```

```tsx
// apps/mobile/src/features/chat/screens/ChatScreen.tsx
<MessageResultCard
  messageId={message.message_id}
  actorLabel={getActorLabel(message.actor_type)}
  actorType={message.actor_type}
  messageType={message.message_type}
  text={presentRuntimeMessageText(getMessageText(message.message_type, message.text))}
  createdAt={message.created_at}
/>
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `npm.cmd test -- src/features/chat/utils/presentRuntimeMessageText.test.ts src/features/chat/screens/ChatScreen.test.tsx --runInBand`

Expected: PASS with business-language default actions and debug-only legacy panel wording.

- [x] **Step 5: Commit**

```bash
git add apps/mobile/src/features/chat/utils/presentRuntimeMessageText.ts apps/mobile/src/features/chat/utils/presentRuntimeMessageText.test.ts apps/mobile/src/features/chat/components/GuidedEntryDock.tsx apps/mobile/src/features/chat/components/MockMediaEntryPanel.tsx apps/mobile/src/features/chat/screens/ChatScreen.tsx apps/mobile/src/features/chat/screens/ChatScreen.test.tsx
git commit -m "feat: de-demoize workbench default path"
```

---


### Task 5: Backend User-Facing Runtime Copy Cleanup

**Files:**
- Modify: `backend/app/runtime/summarizer.py`
- Modify: `backend/app/runtime/processor.py`
- Modify: `backend/app/api/routes/confirmations.py`
- Modify: `backend/app/services/approved_stock_in_commits.py`
- Modify: `backend/app/services/approved_stock_out_commits.py`
- Modify: `backend/app/services/approved_receipt_stock_in_commits.py`
- Modify: `backend/tests/test_runtime_processor.py`
- Modify: `backend/tests/test_inventory_commit_service.py`

- [x] **Step 1: Write the failing tests**

```python
# backend/tests/test_runtime_processor.py
def test_process_task_run_uses_frontline_result_summary_copy(db_session) -> None:
    result = process_task_run(db_session, task_run_id=_seed_voice_query_task_run(db_session))
    task_run = db_session.get(TaskRun, result.task_run_id)
    assert task_run.result_summary == "\u5df2\u8bb0\u5f55\u67e5\u8d27\u8bf7\u6c42\uff1acheck stock left for cola"


# backend/tests/test_inventory_commit_service.py
def test_commit_approved_stock_in_confirmation_writes_frontline_message_copy(db_session) -> None:
    result = commit_approved_stock_in_confirmation(
        db_session,
        confirmation_id=_seed_pending_stock_in_confirmation(db_session),
        owner_actor_id="owner_default",
        resolution_payload={"item_name": "Cola", "quantity": 3, "unit": "box", "price": 12.5},
    )
    assert "Mock runtime" not in result.runtime_message_text
    assert "\u5df2\u5b8c\u6210\u5165\u5e93" in result.runtime_message_text
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$env:PYTHONPATH='backend'; python -m pytest backend/tests/test_runtime_processor.py backend/tests/test_inventory_commit_service.py -q`

Expected: FAIL because the current backend summaries and runtime messages still emit `Mock runtime` wording.

- [x] **Step 3: Write the minimal implementation**

```python
# backend/app/runtime/summarizer.py
def summarize_completed_task(*, task_type: str, transcript: str | None, payload: dict[str, object] | None = None) -> tuple[str, str]:
    normalized_transcript = (transcript or "").strip()
    normalized_payload = payload or {}

    if task_type == "voice-stock-query":
        return (
            f"\u5df2\u8bb0\u5f55\u67e5\u8d27\u8bf7\u6c42\uff1a{normalized_transcript or '\u67e5\u8d27'}",
            "\u5df2\u6536\u5230\u67e5\u8d27\u8bf7\u6c42\uff0c\u8bf7\u67e5\u770b\u5f53\u524d\u5e93\u5b58\u7ed3\u679c\u3002",
        )
    if task_type == "photo-stock-query":
        item_name = str(normalized_payload.get("item_name") or "\u8bc6\u522b\u5546\u54c1")
        stock = normalized_payload.get("stock")
        unit = str(normalized_payload.get("unit") or normalized_payload.get("packaging_hint") or "\u4ef6")
        return (
            f"\u5df2\u8bb0\u5f55\u62cd\u7167\u67e5\u8d27\uff1a{item_name}",
            f"\u5df2\u8bc6\u522b {item_name}\uff0c\u5f53\u524d\u5e93\u5b58 {stock} {unit}\u3002",
        )
    if task_type == "receipt-ocr":
        total_amount = normalized_payload.get("total_amount") or "\u5f85\u786e\u8ba4"
        return (
            f"\u5df2\u5b8c\u6210\u7968\u636e\u8bc6\u522b\uff1a\u603b\u989d {total_amount}",
            f"\u7968\u636e\u8bc6\u522b\u5df2\u5b8c\u6210\uff0c\u8bf7\u6838\u5bf9\u91d1\u989d\u4e0e\u6761\u76ee\u3002\u603b\u989d\uff1a{total_amount}\u3002",
        )
    return (
        f"\u5df2\u8bb0\u5f55\u5165\u5e93\u8bf7\u6c42\uff1a{normalized_transcript or '\u5165\u5e93'}",
        "\u5df2\u6536\u5230\u5165\u5e93\u8bf7\u6c42\uff0c\u8bf7\u7ee7\u7eed\u786e\u8ba4\u540e\u63d0\u4ea4\u3002",
    )


def summarize_failed_task(*, error_code: str, error_message: str) -> tuple[str, str]:
    return (
        f"\u4efb\u52a1\u5931\u8d25\uff1a{error_code}",
        f"\u5f53\u524d\u4efb\u52a1\u6682\u65f6\u65e0\u6cd5\u5b8c\u6210\uff1a{error_message}",
    )
```

```python
# backend/app/runtime/processor.py
text = "\u8bf7\u786e\u8ba4\u7968\u636e\u6761\u76ee\u540e\u518d\u63d0\u4ea4\u5e93\u5b58\u3002"
text = "\u8bf7\u786e\u8ba4\u51fa\u5e93\u4fe1\u606f\u540e\u518d\u63d0\u4ea4\u3002"
text = "\u8bf7\u786e\u8ba4\u5165\u5e93\u4fe1\u606f\u540e\u518d\u63d0\u4ea4\u3002"
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `$env:PYTHONPATH='backend'; python -m pytest backend/tests/test_runtime_processor.py backend/tests/test_inventory_commit_service.py -q`

Expected: PASS with no remaining `Mock runtime` strings in the exercised user-facing paths.

- [x] **Step 5: Commit**

```bash
git add backend/app/runtime/summarizer.py backend/app/runtime/processor.py backend/app/api/routes/confirmations.py backend/app/services/approved_stock_in_commits.py backend/app/services/approved_stock_out_commits.py backend/app/services/approved_receipt_stock_in_commits.py backend/tests/test_runtime_processor.py backend/tests/test_inventory_commit_service.py
git commit -m "feat: replace mock runtime user copy"
```

---

### Task 6: Ledger Rescue, Debug Demotion, And Manual Trial-Shell Verification

**Files:**
- Modify: `apps/mobile/src/features/ledger/screens/LedgerScreen.tsx`
- Modify: `apps/mobile/src/features/ledger/screens/LedgerScreen.test.tsx`
- Modify: `apps/mobile/src/shared/ui/DebugDisclosure.tsx`
- Create: `project_docs/mobile-trial-shell-checklist.md`

- [x] **Step 1: Write the failing tests**

```ts
// apps/mobile/src/features/ledger/screens/LedgerScreen.test.tsx
it("renders readable copy for search, action panel, and activity timeline", async () => {
  render(<LedgerScreen />);
  expect(await screen.findByText("\u5e93\u5b58\u53f0\u8d26")).toBeTruthy();
  expect(screen.getByText("\u641c\u7d22\u5e93\u5b58")).toBeTruthy();
  expect(screen.getByText("\u5e93\u5b58\u5de5\u4f5c\u533a")).toBeTruthy();
  expect(screen.getByText("\u6700\u8fd1\u6d3b\u52a8")).toBeTruthy();
});

it("uses a secondary debug disclosure treatment", () => {
  render(<DebugDisclosure title="\u8c03\u8bd5\u5de5\u5177"><Text>Hidden</Text></DebugDisclosure>);
  expect(screen.getByText("\u5c55\u5f00")).toBeTruthy();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm.cmd test -- src/features/ledger/screens/LedgerScreen.test.tsx --runInBand`

Expected: FAIL because the ledger still contains mojibake copy and the debug treatment is not yet explicitly secondary enough.

- [x] **Step 3: Write the minimal implementation**

```tsx
// apps/mobile/src/features/ledger/screens/LedgerScreen.tsx
<AppScreen title="\u5e93\u5b58\u53f0\u8d26" subtitle="\u67e5\u770b\u5e93\u5b58\u3001\u4fee\u6b63\u6570\u91cf\u5e76\u8ffd\u8e2a\u6700\u8fd1\u6d3b\u52a8\u3002">
  <SurfaceCard emphasis="outlined">
    <SectionHeader title="\u641c\u7d22\u5e93\u5b58" subtitle="\u8f93\u5165\u5546\u54c1\u540d\u79f0\uff0c\u5feb\u901f\u7b5b\u9009\u5e93\u5b58\u5361\u7247\u3002" />
    <AppTextField
      label="\u641c\u7d22\u5e93\u5b58"
      testID="ledger-search-input"
      placeholder="\u4f8b\u5982\uff1a\u82f9\u679c\u3001\u53ef\u4e50"
      value={searchText}
      onChangeText={setSearchText}
    />
  </SurfaceCard>
  <SectionHeader title="\u5e93\u5b58\u5de5\u4f5c\u533a" subtitle="\u4ece\u5361\u7247\u76f4\u63a5\u53d1\u8d77\u4fee\u6b63\u6216\u51fa\u5e93\u3002" />
  <SectionHeader title="\u6700\u8fd1\u6d3b\u52a8" subtitle="\u6309\u65f6\u95f4\u67e5\u770b\u5e93\u5b58\u76f8\u5173\u64cd\u4f5c\u8bb0\u5f55\u3002" />
</AppScreen>
```

```tsx
// apps/mobile/src/shared/ui/DebugDisclosure.tsx
<Pressable accessibilityLabel={title} style={[styles.trigger, styles.secondaryTrigger]}>
  <Text style={styles.title}>{title}</Text>
  <Text style={styles.chevron}>{isOpen ? "\u6536\u8d77" : "\u5c55\u5f00"}</Text>
</Pressable>
```

```md
# project_docs/mobile-trial-shell-checklist.md
1. Launch Expo Go on Android and confirm the login screen renders readable Chinese copy.
2. Sign in and verify the dashboard shows connection health instead of raw debug details.
3. Open the workbench and confirm the default entry actions use business-language labels.
4. Trigger one task flow and confirm no user-visible `Mock runtime` wording remains.
5. Open the ledger and verify search, action, and activity sections are readable.
6. Expand debug tools and confirm they remain reachable but secondary.
```

- [ ] **Step 4: Run the tests and manual verification**

Run:

```bash
npm.cmd test -- --runInBand
$env:PYTHONPATH='backend'; python -m pytest backend/tests -q
```

Manual:

```bash
cd C:\Users\roco2\Downloads\Business\apps\mobile
$env:EXPO_PUBLIC_API_BASE_URL="http://192.168.1.4:8001"
npm.cmd run start -- --host lan --port 8081 --clear
```

Expected:

- mobile Jest passes
- backend pytest passes
- Android Expo Go can complete the checklist in `project_docs/mobile-trial-shell-checklist.md`

- [ ] **Step 5: Commit**

```bash
git add apps/mobile/src/features/ledger/screens/LedgerScreen.tsx apps/mobile/src/features/ledger/screens/LedgerScreen.test.tsx apps/mobile/src/shared/ui/DebugDisclosure.tsx project_docs/mobile-trial-shell-checklist.md
git commit -m "feat: harden ledger and trial-shell verification"
```

---

## Spec Coverage Check

- Copy and state normalization: Task 1
- Connectivity baseline and Expo/device API behavior: Task 2
- Login hardening: Task 3
- Dashboard operational clarity: Task 3
- Workbench trust, de-demoization, and confirmation-safe default path: Task 4
- Separation of user-facing copy from backend mock posture: Task 5
- Ledger usability rescue: Task 6
- Debug tool demotion: Tasks 3, 4, and 6
- Android/Expo trial-shell manual verification: Task 6

## Placeholder Scan

- No placeholder markers remain.
- Every code-writing step includes an explicit code block.
- Every verification step includes concrete commands and expected outcomes.

## Type Consistency Check

- Shared copy helpers are introduced before screens consume them.
- API base URL resolution is introduced before `client.ts` switches to it.
- Workbench connection copy is introduced before the workbench header/screens rely on it.
- Frontend runtime message presentation is introduced before `ChatScreen.tsx` consumes it.
- Backend summary/message changes are paired with backend tests that assert the new copy.

