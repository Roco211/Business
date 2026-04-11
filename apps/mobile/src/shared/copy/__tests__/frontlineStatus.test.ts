import { FRONTLINE_STATUS_COPY, normalizeRuntimeMessage } from "../frontlineStatus";

describe("frontlineStatus", () => {
  it("maps leaked mock runtime copy to stable frontline wording", () => {
    expect(
      normalizeRuntimeMessage("Mock runtime: stock query accepted and queued for simulation."),
    ).toBe(FRONTLINE_STATUS_COPY.realtimeDegraded);
  });

  it("keeps network fallback copy stable", () => {
    expect(FRONTLINE_STATUS_COPY.networkUnavailable).toBe("当前无法连接门店服务，请检查网络后重试。");
  });
});
