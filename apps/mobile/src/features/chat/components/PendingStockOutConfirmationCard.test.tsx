import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import { PendingStockOutConfirmationCard } from "./PendingStockOutConfirmationCard";
import { useApproveConfirmationMutation } from "../hooks/useApproveConfirmationMutation";
import { ChatPendingConfirmationRecord } from "../hooks/useChatPendingConfirmationsQuery";
import { useRejectConfirmationMutation } from "../hooks/useRejectConfirmationMutation";

jest.mock("../hooks/useApproveConfirmationMutation");
jest.mock("../hooks/useRejectConfirmationMutation");

const mockedUseApproveConfirmationMutation = useApproveConfirmationMutation as jest.MockedFunction<
  typeof useApproveConfirmationMutation
>;
const mockedUseRejectConfirmationMutation = useRejectConfirmationMutation as jest.MockedFunction<
  typeof useRejectConfirmationMutation
>;

function buildConfirmation(
  fields: Partial<ChatPendingConfirmationRecord["fields"]> = {},
): ChatPendingConfirmationRecord {
  return {
    confirmation_id: "conf_stock_out_1",
    session_id: "sess_1",
    task_run_id: "task_1",
    confirmation_type: "stock-out",
    status: "pending",
    fields: {
      summary: "Please confirm stock-out.",
      transcript: "Stock out transcript",
      draft_fields: {
        item_id: "item_1",
        item_name: "Red Bull 250ml",
        stock_out_quantity: 3,
        reason: "Broken package",
      } as Record<string, unknown>,
      reason: "Broken package",
      ...fields,
    },
  };
}

describe("PendingStockOutConfirmationCard", () => {
  const approveConfirmation = jest.fn();
  const rejectConfirmation = jest.fn();

  beforeEach(() => {
    approveConfirmation.mockReset();
    rejectConfirmation.mockReset();

    approveConfirmation.mockResolvedValue({ data: { confirmation_id: "conf_stock_out_1", status: "approved" } });
    rejectConfirmation.mockResolvedValue({ data: { confirmation_id: "conf_stock_out_1", status: "rejected" } });

    mockedUseApproveConfirmationMutation.mockReturnValue({
      isSubmitting: false,
      error: null,
      approveConfirmation,
    } as never);
    mockedUseRejectConfirmationMutation.mockReturnValue({
      isSubmitting: false,
      error: null,
      rejectConfirmation,
    } as never);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it("syncs editable fields with refreshed confirmation draft fields on rerender", async () => {
    const onResolved = jest.fn();
    const { rerender } = render(
      <PendingStockOutConfirmationCard confirmation={buildConfirmation()} onResolved={onResolved} />,
    );

    fireEvent.changeText(screen.getByDisplayValue("Red Bull 250ml"), "User Edited Name");
    fireEvent.changeText(screen.getByDisplayValue("3"), "99");
    fireEvent.changeText(screen.getByDisplayValue("Broken package"), "User Edited Reason");

    rerender(
      <PendingStockOutConfirmationCard
        confirmation={buildConfirmation({
          draft_fields: {
            item_id: "item_2",
            item_name: "Sprite 330ml",
            stock_out_quantity: 5,
            reason: "Expired",
          } as Record<string, unknown>,
          reason: "Expired",
        })}
        onResolved={onResolved}
      />,
    );

    expect(screen.getByDisplayValue("Sprite 330ml")).toBeTruthy();
    expect(screen.getByDisplayValue("5")).toBeTruthy();
    expect(screen.getByDisplayValue("Expired")).toBeTruthy();
    expect(screen.queryByDisplayValue("User Edited Name")).toBeNull();
    expect(screen.queryByDisplayValue("99")).toBeNull();
    expect(screen.queryByDisplayValue("User Edited Reason")).toBeNull();

    fireEvent.press(screen.getByTestId("confirm-approve-conf_stock_out_1"));

    await waitFor(() => {
      expect(approveConfirmation).toHaveBeenCalledWith("conf_stock_out_1", {
        item_id: "item_2",
        item_name: "Sprite 330ml",
        stock_out_quantity: 5,
        reason: "Expired",
      });
      expect(onResolved).toHaveBeenCalledTimes(1);
    });
  });
});
