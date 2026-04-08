import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";

import { PendingReceiptConfirmationCard } from "./PendingReceiptConfirmationCard";
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
    confirmation_id: "conf_receipt_1",
    session_id: "sess_1",
    task_run_id: "task_1",
    confirmation_type: "receipt-stock-in-batch",
    status: "pending",
    fields: {
      summary: "Please confirm the receipt line items before committing inventory.",
      ocr_document_id: "ocr_1",
      total_amount: 147,
      low_confidence_fields: [],
      draft_items: [
        {
          line_id: "line_1",
          item_id: null,
          item_name: "Red Bull 250ml",
          quantity: 3,
          unit: "can",
          price: 41,
        },
        {
          line_id: "line_2",
          item_id: null,
          item_name: "Coca Cola 500ml",
          quantity: 2,
          unit: "bottle",
          price: 12,
        },
      ],
      ...fields,
    },
  };
}

describe("PendingReceiptConfirmationCard", () => {
  const approveConfirmation = jest.fn();
  const rejectConfirmation = jest.fn();

  beforeEach(() => {
    approveConfirmation.mockReset();
    rejectConfirmation.mockReset();

    approveConfirmation.mockResolvedValue({ data: { confirmation_id: "conf_receipt_1", status: "approved" } });
    rejectConfirmation.mockResolvedValue({ data: { confirmation_id: "conf_receipt_1", status: "rejected" } });

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

  it("shows summary metrics first and only renders line editors after opening details", () => {
    render(
      <PendingReceiptConfirmationCard
        confirmation={buildConfirmation({ low_confidence_fields: ["line_2.price", "line_1.quantity"] })}
        onResolved={jest.fn()}
      />,
    );

    expect(screen.getByText("已识别 2 条明细")).toBeTruthy();
    expect(screen.getByText("总额 147")).toBeTruthy();
    expect(screen.getByText("需要复核 2 项")).toBeTruthy();
    expect(screen.getByLabelText("查看明细")).toBeTruthy();

    expect(screen.queryByDisplayValue("Red Bull 250ml")).toBeNull();
    expect(screen.queryByDisplayValue("Coca Cola 500ml")).toBeNull();

    fireEvent.press(screen.getByLabelText("查看明细"));

    expect(screen.getByLabelText("收起明细")).toBeTruthy();
    expect(screen.getByDisplayValue("Red Bull 250ml")).toBeTruthy();
    expect(screen.getByDisplayValue("Coca Cola 500ml")).toBeTruthy();

    fireEvent.press(screen.getByLabelText("收起明细"));
    expect(screen.queryByDisplayValue("Red Bull 250ml")).toBeNull();
  });

  it("keeps approve payload shape and uses edited line-item values", async () => {
    const onResolved = jest.fn();

    render(<PendingReceiptConfirmationCard confirmation={buildConfirmation()} onResolved={onResolved} />);

    fireEvent.press(screen.getByLabelText("查看明细"));
    fireEvent.changeText(screen.getByPlaceholderText("数量 1"), "4");
    fireEvent.changeText(screen.getByPlaceholderText("单价 2"), "13");
    fireEvent.press(screen.getByTestId("confirm-approve-conf_receipt_1"));

    await waitFor(() => {
      expect(approveConfirmation).toHaveBeenCalledWith("conf_receipt_1", {
        items: [
          {
            line_id: "line_1",
            item_id: null,
            item_name: "Red Bull 250ml",
            quantity: 4,
            unit: "can",
            price: 41,
          },
          {
            line_id: "line_2",
            item_id: null,
            item_name: "Coca Cola 500ml",
            quantity: 2,
            unit: "bottle",
            price: 13,
          },
        ],
      });
      expect(onResolved).toHaveBeenCalledTimes(1);
    });
  });

  it("syncs editable line items with refreshed confirmation draft items on rerender", async () => {
    const onResolved = jest.fn();
    const { rerender } = render(
      <PendingReceiptConfirmationCard confirmation={buildConfirmation()} onResolved={onResolved} />,
    );

    fireEvent.press(screen.getByLabelText("查看明细"));
    fireEvent.changeText(screen.getByDisplayValue("Red Bull 250ml"), "User Edited Name");
    fireEvent.changeText(screen.getByDisplayValue("3"), "99");

    rerender(
      <PendingReceiptConfirmationCard
        confirmation={buildConfirmation({
          draft_items: [
            {
              line_id: "line_1",
              item_id: null,
              item_name: "Sprite 330ml",
              quantity: 5,
              unit: "can",
              price: 77,
            },
            {
              line_id: "line_2",
              item_id: null,
              item_name: "Coca Cola 500ml",
              quantity: 2,
              unit: "bottle",
              price: 12,
            },
          ],
        })}
        onResolved={onResolved}
      />,
    );

    expect(screen.getByDisplayValue("Sprite 330ml")).toBeTruthy();
    expect(screen.getByDisplayValue("5")).toBeTruthy();
    expect(screen.queryByDisplayValue("User Edited Name")).toBeNull();
    expect(screen.queryByDisplayValue("99")).toBeNull();

    fireEvent.press(screen.getByTestId("confirm-approve-conf_receipt_1"));

    await waitFor(() => {
      expect(approveConfirmation).toHaveBeenCalledWith("conf_receipt_1", {
        items: [
          {
            line_id: "line_1",
            item_id: null,
            item_name: "Sprite 330ml",
            quantity: 5,
            unit: "can",
            price: 77,
          },
          {
            line_id: "line_2",
            item_id: null,
            item_name: "Coca Cola 500ml",
            quantity: 2,
            unit: "bottle",
            price: 12,
          },
        ],
      });
      expect(onResolved).toHaveBeenCalledTimes(1);
    });
  });
});
