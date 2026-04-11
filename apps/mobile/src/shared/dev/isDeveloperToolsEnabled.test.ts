import { isDeveloperToolsEnabled } from "./isDeveloperToolsEnabled";

describe("isDeveloperToolsEnabled", () => {
  const originalFlag = (globalThis as { __AI_STORE_MANAGER_ENABLE_DEV_TOOLS__?: boolean })
    .__AI_STORE_MANAGER_ENABLE_DEV_TOOLS__;

  afterEach(() => {
    if (originalFlag === undefined) {
      delete (globalThis as { __AI_STORE_MANAGER_ENABLE_DEV_TOOLS__?: boolean })
        .__AI_STORE_MANAGER_ENABLE_DEV_TOOLS__;
    } else {
      (globalThis as { __AI_STORE_MANAGER_ENABLE_DEV_TOOLS__?: boolean })
        .__AI_STORE_MANAGER_ENABLE_DEV_TOOLS__ = originalFlag;
    }
  });

  it("returns false for the default user path", () => {
    delete (globalThis as { __AI_STORE_MANAGER_ENABLE_DEV_TOOLS__?: boolean })
      .__AI_STORE_MANAGER_ENABLE_DEV_TOOLS__;
    expect(isDeveloperToolsEnabled()).toBe(false);
  });

  it("returns true only when the explicit developer flag is enabled in a dev build", () => {
    (globalThis as { __AI_STORE_MANAGER_ENABLE_DEV_TOOLS__?: boolean })
      .__AI_STORE_MANAGER_ENABLE_DEV_TOOLS__ = true;
    expect(isDeveloperToolsEnabled()).toBe(true);
  });
});
