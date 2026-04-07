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


export function PendingStockOutConfirmationCard({
  confirmation,
  onResolved,
}: {
  confirmation: ChatPendingConfirmationRecord;
  onResolved: () => void;
}) {
  const draftFields = confirmation.fields.draft_fields ?? {};
  const [itemName, setItemName] = useState(toInputValue(draftFields.item_name));
  const [quantity, setQuantity] = useState(toInputValue(draftFields.stock_out_quantity));
  const [reason, setReason] = useState(
    toInputValue(draftFields.reason ?? confirmation.fields.reason ?? "stock out via chat"),
  );
  const [isResolved, setIsResolved] = useState(false);
  const approveMutation = useApproveConfirmationMutation();
  const rejectMutation = useRejectConfirmationMutation();
  const error = approveMutation.error ?? rejectMutation.error;
  const isSubmitting = approveMutation.isSubmitting || rejectMutation.isSubmitting;

  async function handleApprove() {
    const payload: Record<string, unknown> = {
      item_name: itemName.trim(),
      stock_out_quantity: Number(quantity),
      reason: reason.trim(),
    };
    if (draftFields.item_id) {
      payload.item_id = draftFields.item_id;
    }

    const result = await approveMutation.approveConfirmation(confirmation.confirmation_id, payload);
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
      title="Pending stock-out confirmation"
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
        label="Stock-out quantity"
        placeholder="Stock-out quantity"
        keyboardType="numeric"
        value={quantity}
        onChangeText={setQuantity}
      />
      <AppTextField label="Reason" placeholder="Reason" value={reason} onChangeText={setReason} />
    </ConfirmationCardShell>
  );
}
