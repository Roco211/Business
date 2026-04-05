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
      <Text>Pending confirmation</Text>
      {confirmation.fields.summary ? <Text>{confirmation.fields.summary}</Text> : null}
      {confirmation.fields.transcript ? <Text>{confirmation.fields.transcript}</Text> : null}

      <TextInput placeholder="Item name" value={itemName} onChangeText={setItemName} />
      <TextInput
        placeholder="Quantity"
        keyboardType="numeric"
        value={quantity}
        onChangeText={setQuantity}
      />
      <TextInput placeholder="Unit" value={unit} onChangeText={setUnit} />
      <TextInput placeholder="Price" keyboardType="numeric" value={price} onChangeText={setPrice} />

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
