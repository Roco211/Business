import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { AppTextField, color, space } from "../../../shared/ui";
import { ConfirmationCardShell } from "./ConfirmationCardShell";
import { useApproveConfirmationMutation } from "../hooks/useApproveConfirmationMutation";
import { ChatPendingConfirmationRecord, ReceiptDraftItem } from "../hooks/useChatPendingConfirmationsQuery";
import { useRejectConfirmationMutation } from "../hooks/useRejectConfirmationMutation";

const COPY = {
  title: "票据入库确认",
  approve: "确认票据",
  reject: "驳回票据",
  approving: "提交票据中...",
  rejecting: "驳回中...",
  ocrPrefix: "OCR：",
  totalPrefix: "总额：",
  linePrefix: "行 ",
  itemNamePrefix: "商品名称 ",
  quantityPrefix: "数量 ",
  unitPrefix: "单位 ",
  pricePrefix: "单价 ",
} as const;

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
  const [isResolved, setIsResolved] = useState(false);
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
      title={COPY.title}
      summary={confirmation.fields.summary}
      transcript={
        confirmation.fields.ocr_document_id
          ? `${COPY.ocrPrefix}${confirmation.fields.ocr_document_id}`
          : undefined
      }
      error={error}
      approveLabel={COPY.approve}
      rejectLabel={COPY.reject}
      approveLoadingLabel={COPY.approving}
      rejectLoadingLabel={COPY.rejecting}
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
      {confirmation.fields.total_amount !== undefined ? (
        <Text style={styles.totalAmount}>
          {COPY.totalPrefix}
          {confirmation.fields.total_amount}
        </Text>
      ) : null}
      {items.map((item, index) => (
        <View key={item.lineId} style={styles.lineEditor}>
          <Text style={styles.lineTitle}>
            {COPY.linePrefix}
            {index + 1}
          </Text>
          <AppTextField
            label={`${COPY.itemNamePrefix}${index + 1}`}
            placeholder={`${COPY.itemNamePrefix}${index + 1}`}
            value={item.itemName}
            onChangeText={(value) => updateItem(index, { itemName: value })}
          />
          <AppTextField
            label={`${COPY.quantityPrefix}${index + 1}`}
            placeholder={`${COPY.quantityPrefix}${index + 1}`}
            keyboardType="numeric"
            value={item.quantity}
            onChangeText={(value) => updateItem(index, { quantity: value })}
          />
          <AppTextField
            label={`${COPY.unitPrefix}${index + 1}`}
            placeholder={`${COPY.unitPrefix}${index + 1}`}
            value={item.unit}
            onChangeText={(value) => updateItem(index, { unit: value })}
          />
          <AppTextField
            label={`${COPY.pricePrefix}${index + 1}`}
            placeholder={`${COPY.pricePrefix}${index + 1}`}
            keyboardType="numeric"
            value={item.price}
            onChangeText={(value) => updateItem(index, { price: value })}
          />
        </View>
      ))}
    </ConfirmationCardShell>
  );
}

const styles = StyleSheet.create({
  totalAmount: {
    color: color.fgSecondary,
    fontSize: 14,
  },
  lineEditor: {
    borderColor: color.borderSubtle,
    borderRadius: 10,
    borderWidth: 1,
    gap: space.s8,
    padding: space.s12,
  },
  lineTitle: {
    color: color.fgPrimary,
    fontSize: 14,
    fontWeight: "600",
  },
});
