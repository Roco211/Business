import { useState } from "react";
import { Button, Text, TextInput, View } from "react-native";

import { useApproveConfirmationMutation } from "../hooks/useApproveConfirmationMutation";
import { ChatPendingConfirmationRecord, ReceiptDraftItem } from "../hooks/useChatPendingConfirmationsQuery";
import { useRejectConfirmationMutation } from "../hooks/useRejectConfirmationMutation";


function toInputValue(value: number | string | null | undefined) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value);
}


type EditableReceiptLine = {
  lineId: string;
  itemId: string;
  itemName: string;
  quantity: string;
  unit: string;
  price: string;
};


function toEditableLine(line: ReceiptDraftItem, index: number): EditableReceiptLine {
  return {
    lineId: line.line_id ?? `line_${index + 1}`,
    itemId: line.item_id ?? "",
    itemName: toInputValue(line.item_name),
    quantity: toInputValue(line.quantity),
    unit: toInputValue(line.unit),
    price: toInputValue(line.price),
  };
}


export function PendingReceiptConfirmationCard({
  confirmation,
  onResolved,
}: {
  confirmation: ChatPendingConfirmationRecord;
  onResolved: () => void;
}) {
  const draftItems = confirmation.fields.draft_items ?? [];
  const [items, setItems] = useState<EditableReceiptLine[]>(
    draftItems.map((item, index) => toEditableLine(item, index)),
  );
  const approveMutation = useApproveConfirmationMutation();
  const rejectMutation = useRejectConfirmationMutation();
  const error = approveMutation.error ?? rejectMutation.error;
  const isSubmitting = approveMutation.isSubmitting || rejectMutation.isSubmitting;

  function updateItem(index: number, patch: Partial<EditableReceiptLine>) {
    setItems((current) =>
      current.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)),
    );
  }

  async function handleApprove() {
    const result = await approveMutation.approveConfirmation(confirmation.confirmation_id, {
      items: items.map((item) => ({
        line_id: item.lineId,
        item_id: item.itemId.trim() || null,
        item_name: item.itemName.trim(),
        quantity: Number(item.quantity),
        unit: item.unit.trim(),
        price: Number(item.price),
      })),
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
      <Text>Receipt confirmation</Text>
      {confirmation.fields.summary ? <Text>{confirmation.fields.summary}</Text> : null}
      {confirmation.fields.ocr_document_id ? <Text>OCR: {confirmation.fields.ocr_document_id}</Text> : null}
      {confirmation.fields.total_amount !== undefined ? <Text>Total: {confirmation.fields.total_amount}</Text> : null}

      {items.map((item, index) => (
        <View key={item.lineId}>
          <Text>Line {index + 1}</Text>
          <TextInput
            placeholder={`Item name ${index + 1}`}
            value={item.itemName}
            onChangeText={(value) => updateItem(index, { itemName: value })}
          />
          <TextInput
            placeholder={`Quantity ${index + 1}`}
            keyboardType="numeric"
            value={item.quantity}
            onChangeText={(value) => updateItem(index, { quantity: value })}
          />
          <TextInput
            placeholder={`Unit ${index + 1}`}
            value={item.unit}
            onChangeText={(value) => updateItem(index, { unit: value })}
          />
          <TextInput
            placeholder={`Price ${index + 1}`}
            keyboardType="numeric"
            value={item.price}
            onChangeText={(value) => updateItem(index, { price: value })}
          />
        </View>
      ))}

      {error ? <Text>{error}</Text> : null}

      <Button
        title={approveMutation.isSubmitting ? "Approving receipt..." : "Approve Receipt"}
        onPress={() => {
          void handleApprove();
        }}
        disabled={isSubmitting}
      />
      <Button
        title={rejectMutation.isSubmitting ? "Rejecting..." : "Reject Receipt"}
        onPress={() => {
          void handleReject();
        }}
        disabled={isSubmitting}
      />
    </View>
  );
}
