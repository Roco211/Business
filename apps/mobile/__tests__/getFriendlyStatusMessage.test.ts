import { getFriendlyStatusMessage } from "../src/shared/copy/getFriendlyStatusMessage";
import { FRONTLINE_STATUS_COPY } from "../src/shared/copy/frontlineStatus";

describe("getFriendlyStatusMessage", () => {
  it("uses the fallback when the message is empty", () => {
    expect(getFriendlyStatusMessage("   ", "请稍后再试。")).toBe("请稍后再试。");
  });

  it("keeps chinese messages untouched", () => {
    expect(getFriendlyStatusMessage("库存同步失败", "请稍后再试。")).toBe("库存同步失败");
  });

  it("converts network failures into stable frontline network copy", () => {
    expect(
      getFriendlyStatusMessage(
        "Cannot reach API at http://127.0.0.1:8001 (Network request failed)",
        "请稍后再试。",
      ),
    ).toBe(FRONTLINE_STATUS_COPY.networkUnavailable);
  });

  it("normalizes leaked mock runtime task failures into stable task-failed copy", () => {
    expect(
      getFriendlyStatusMessage(
        "Mock runtime could not process this task because no simulation route matched.",
        "请稍后再试。",
      ),
    ).toBe(FRONTLINE_STATUS_COPY.taskFailed);
  });

  it("preserves english business errors instead of collapsing them to the fallback", () => {
    expect(getFriendlyStatusMessage("Reset failed", "请稍后再试。")).toBe("Reset failed");
  });
});
