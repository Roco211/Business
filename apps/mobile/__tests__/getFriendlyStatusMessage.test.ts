import { getFriendlyStatusMessage } from "../src/shared/copy/getFriendlyStatusMessage";

describe("getFriendlyStatusMessage", () => {
  it("uses the fallback when the message is empty", () => {
    expect(getFriendlyStatusMessage("   ", "请稍后再试。")).toBe("请稍后再试。");
  });

  it("keeps chinese messages untouched", () => {
    expect(getFriendlyStatusMessage("库存同步失败", "请稍后再试。")).toBe("库存同步失败");
  });

  it("maps only explicit network failures to the friendly network copy", () => {
    expect(
      getFriendlyStatusMessage(
        "Cannot reach API at http://127.0.0.1:8001 (Network request failed)",
        "请稍后再试。",
      ),
    ).toBe("当前无法连接门店服务，请检查网络后重试。");
  });

  it("preserves english business errors instead of collapsing them to the fallback", () => {
    expect(getFriendlyStatusMessage("Reset failed", "请稍后再试。")).toBe("Reset failed");
  });
});
