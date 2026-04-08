import { FRONTLINE_STATUS_COPY } from "../../../shared/copy/frontlineStatus";
import { presentRuntimeMessageText } from "./presentRuntimeMessageText";

describe("presentRuntimeMessageText", () => {
  it("maps leaked mock stock-query copy to stable frontline wording", () => {
    expect(
      presentRuntimeMessageText("Mock runtime: stock query accepted and queued for simulation."),
    ).toBe(FRONTLINE_STATUS_COPY.realtimeDegraded);
  });

  it("removes a mock runtime prefix from generic runtime text", () => {
    expect(presentRuntimeMessageText("Mock runtime: Inventory review queued.")).toBe(
      "Inventory review queued.",
    );
  });
});
