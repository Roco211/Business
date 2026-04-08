import { FRONTLINE_STATUS_COPY } from "../../../shared/copy/frontlineStatus";
import { presentRuntimeMessageText } from "./presentRuntimeMessageText";

describe("presentRuntimeMessageText", () => {
  it("maps leaked mock stock-query copy to stable frontline wording", () => {
    expect(
      presentRuntimeMessageText("Mock runtime: stock query accepted and queued for simulation.", {
        isRuntimeSystemMessage: true,
      }),
    ).toBe(FRONTLINE_STATUS_COPY.realtimeDegraded);
  });

  it("removes a mock runtime prefix from generic runtime text", () => {
    expect(
      presentRuntimeMessageText("Mock runtime: Inventory review queued.", {
        isRuntimeSystemMessage: true,
      }),
    ).toBe(
      "Inventory review queued.",
    );
  });

  it("does not normalize non-runtime text that starts with mock runtime prefix", () => {
    expect(
      presentRuntimeMessageText("Mock runtime: stock query accepted and queued for simulation."),
    ).toBe("Mock runtime: stock query accepted and queued for simulation.");
  });

  it("returns an empty string for runtime payloads that only contain mock runtime prefix", () => {
    expect(
      presentRuntimeMessageText("Mock runtime:    ", {
        isRuntimeSystemMessage: true,
      }),
    ).toBe("");
  });
});
