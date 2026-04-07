import { useState } from "react";

import { AppTextField } from "../../../shared/ui";
import { ConfirmationCardShell } from "./ConfirmationCardShell";
import { useApproveConfirmationMutation } from "../hooks/useApproveConfirmationMutation";
import { ChatPendingConfirmationRecord } from "../hooks/useChatPendingConfirmationsQuery";
import { useRejectConfirmationMutation } from "../hooks/useRejectConfirmationMutation";

const COPY = {
  title: "待确认入库",
  approve: "确认入库",
  reject: "驳回",
  approving: "提交中...",
  rejecting: "驳回中...",
  itemName: "商品名称",
  quantity: "数量",
  unit: "单位",
  price: "单价",
} as const;

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
      title={COPY.title}
      summary={confirmation.fields.summary}
      transcript={confirmation.fields.transcript}
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
      <AppTextField
        label={COPY.itemName}
        placeholder={COPY.itemName}
        value={itemName}
        onChangeText={setItemName}
      />
      <AppTextField
        label={COPY.quantity}
        placeholder={COPY.quantity}
        keyboardType="numeric"
        value={quantity}
        onChangeText={setQuantity}
      />
      <AppTextField label={COPY.unit} placeholder={COPY.unit} value={unit} onChangeText={setUnit} />
      <AppTextField
        label={COPY.price}
        placeholder={COPY.price}
        keyboardType="numeric"
        value={price}
        onChangeText={setPrice}
      />
    </ConfirmationCardShell>
  );
}
