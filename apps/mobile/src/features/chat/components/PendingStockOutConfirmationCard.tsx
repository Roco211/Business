import { useState } from "react";
import { Button, Text, TextInput, View } from "react-native";

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
    onResolved();
  }

  async function handleReject() {
    const result = await rejectMutation.rejectConfirmation(confirmation.confirmation_id);
    if (result === null) {
      return;
    }
    onResolved();
  }

  return (
    <View>
      <Text>Pending stock-out confirmation</Text>
      {confirmation.fields.summary ? <Text>{confirmation.fields.summary}</Text> : null}
      {confirmation.fields.transcript ? <Text>{confirmation.fields.transcript}</Text> : null}

      <TextInput placeholder="Item name" value={itemName} onChangeText={setItemName} />
      <TextInput
        placeholder="Stock-out quantity"
        keyboardType="numeric"
        value={quantity}
        onChangeText={setQuantity}
      />
      <TextInput placeholder="Reason" value={reason} onChangeText={setReason} />

      {error ? <Text>{error}</Text> : null}

      <Button
        title={approveMutation.isSubmitting ? "Approving..." : "Approve"}
        onPress={() => {
          void handleApprove();
        }}
        disabled={isSubmitting}
      />
      <Button
        title={rejectMutation.isSubmitting ? "Rejecting..." : "Reject"}
        onPress={() => {
          void handleReject();
        }}
        disabled={isSubmitting}
      />
    </View>
  );
}
