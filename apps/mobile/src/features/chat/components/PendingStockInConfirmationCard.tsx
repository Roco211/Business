import { useState } from "react";

import { AppTextField } from "../../../shared/ui";
import { ConfirmationCardShell } from "./ConfirmationCardShell";
import { useApproveConfirmationMutation } from "../hooks/useApproveConfirmationMutation";
import { ChatPendingConfirmationRecord } from "../hooks/useChatPendingConfirmationsQuery";
import { useRejectConfirmationMutation } from "../hooks/useRejectConfirmationMutation";


function toInputValue(value: number | string | null | undefined) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value);
}


export function PendingStockInConfirmationCard({
  confirmation,
  onResolved,
}: {
  confirmation: ChatPendingConfirmationRecord;
  onResolved: () => void;
}) {
  const draftFields = confirmation.fields.draft_fields ?? {};
  const [itemName, setItemName] = useState(toInputValue(draftFields.item_name));
  const [quantity, setQuantity] = useState(toInputValue(draftFields.quantity));
  const [unit, setUnit] = useState(toInputValue(draftFields.unit));
  const [price, setPrice] = useState(toInputValue(draftFields.price));
  const [isResolved, setIsResolved] = useState(false);
  const approveMutation = useApproveConfirmationMutation();
  const rejectMutation = useRejectConfirmationMutation();
  const error = approveMutation.error ?? rejectMutation.error;
  const isSubmitting = approveMutation.isSubmitting || rejectMutation.isSubmitting;

  async function handleApprove() {
    const result = await approveMutation.approveConfirmation(confirmation.confirmation_id, {
      item_name: itemName.trim(),
      quantity: Number(quantity),
      unit: unit.trim(),
      price: Number(price),
    });
    if (result === null) {
      return;
    }
    setIsResolved(true);
    onResolved();
  }

  async function handleReject() {
    const result = await rejectMutation.rejectConfirmation(confirmation.confirmation_id);
    if (result === null) {
      return;
    }
    setIsResolved(true);
    onResolved();
  }

  if (isResolved) {
    return null;
  }

  return (
    <ConfirmationCardShell
      confirmationId={confirmation.confirmation_id}
      title="Pending confirmation"
      summary={confirmation.fields.summary}
      transcript={confirmation.fields.transcript}
      error={error}
      approveLabel="Approve"
      rejectLabel="Reject"
      approveLoadingLabel="Approving..."
      rejectLoadingLabel="Rejecting..."
      isApproveSubmitting={approveMutation.isSubmitting}
      isRejectSubmitting={rejectMutation.isSubmitting}
      isSubmitting={isSubmitting}
      onApprove={() => {
        void handleApprove();
      }}
      onReject={() => {
        void handleReject();
      }}
    >
      <AppTextField
        label="Item name"
        placeholder="Item name"
        value={itemName}
        onChangeText={setItemName}
      />
      <AppTextField
        label="Quantity"
        placeholder="Quantity"
        keyboardType="numeric"
        value={quantity}
        onChangeText={setQuantity}
      />
      <AppTextField label="Unit" placeholder="Unit" value={unit} onChangeText={setUnit} />
      <AppTextField
        label="Price"
        placeholder="Price"
        keyboardType="numeric"
        value={price}
        onChangeText={setPrice}
      />
    </ConfirmationCardShell>
  );
}
