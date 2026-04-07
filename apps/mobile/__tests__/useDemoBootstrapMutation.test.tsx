import { act, renderHook } from "@testing-library/react-native";

import {
  type DemoBootstrapSummaryRecord,
  useDemoBootstrapMutation,
} from "../src/features/dashboard/hooks/useDemoBootstrapMutation";

const DEMO_BOOTSTRAP_SUMMARY: DemoBootstrapSummaryRecord = {
  shop_id: "shop_default",
  session_id: "sess_default",
  inventory_item_count: 3,
  inventory_item_names: ["Coca Cola 500ml", "Cola", "Red Bull 250ml"],
  pending_confirmation_count: 2,
  pending_confirmation_types: ["receipt-stock-in-batch", "stock-out"],
  open_low_stock_alert_count: 1,
  open_low_stock_item_names: ["Cola"],
  message_count: 10,
  task_run_count: 4,
};

describe("useDemoBootstrapMutation", () => {
  afterEach(() => {
    jest.resetAllMocks();
  });

  it("submits demo bootstrap and exposes success state", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        data: DEMO_BOOTSTRAP_SUMMARY,
      }),
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useDemoBootstrapMutation());

    let response: DemoBootstrapSummaryRecord | null = null;
    await act(async () => {
      response = await result.current.runDemoBootstrap();
    });

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/system/demo/bootstrap"),
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(response).toEqual(DEMO_BOOTSTRAP_SUMMARY);
    expect(result.current.isSubmitting).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.successMessage).toBe("演示数据已刷新，可继续体验。");
  });

  it("surfaces backend failure while clearing the success message", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      json: async () => ({
        error: {
          code: "demo_bootstrap_failed",
          message: "Reset failed",
          details: [],
        },
      }),
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useDemoBootstrapMutation());

    let response: DemoBootstrapSummaryRecord | null = DEMO_BOOTSTRAP_SUMMARY;
    await act(async () => {
      response = await result.current.runDemoBootstrap();
    });

    expect(response).toBeNull();
    expect(result.current.isSubmitting).toBe(false);
    expect(result.current.successMessage).toBeNull();
    expect(result.current.error).toBe("演示数据暂时无法重置，请稍后再试。");
  });

  it("lets an in-flight reset resolve after unmount without React warnings", async () => {
    const consoleErrorSpy = jest.spyOn(console, "error").mockImplementation(() => undefined);
    let resolveFetch:
      | ((value: { ok: boolean; json: () => Promise<{ data: DemoBootstrapSummaryRecord }> }) => void)
      | null = null;

    global.fetch = jest.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve;
        }),
    ) as unknown as typeof fetch;

    const { result, unmount } = renderHook(() => useDemoBootstrapMutation());

    let responsePromise: Promise<DemoBootstrapSummaryRecord | null> | null = null;
    act(() => {
      responsePromise = result.current.runDemoBootstrap();
    });

    expect(result.current.isSubmitting).toBe(true);

    unmount();

    await act(async () => {
      resolveFetch?.({
        ok: true,
        json: async () => ({
          data: DEMO_BOOTSTRAP_SUMMARY,
        }),
      });
      await responsePromise;
    });

    expect(consoleErrorSpy).not.toHaveBeenCalled();
    consoleErrorSpy.mockRestore();
  });
});
