import { useEffect, useState } from "react";

import { AppTextField } from "../../../shared/ui";
import { ConfirmationCardShell } from "./ConfirmationCardShell";
import { useApproveConfirmationMutation } from "../hooks/useApproveConfirmationMutation";
import { ChatPendingConfirmationRecord } from "../hooks/useChatPendingConfirmationsQuery";
import { useRejectConfirmationMutation } from "../hooks/useRejectConfirmationMutation";

const COPY = {
  title: "待确认出库",
  approve: "确认出库",
  reject: "驳回",
  approving: "提交中...",
  rejecting: "驳回中...",
  itemName: "商品名称",
  quantity: "出库数量",
  reason: "原因",
  defaultReason: "聊天出库",
} as const;

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
  const draftFieldsSyncKey = JSON.stringify(draftFields);
  const reasonSeed = draftFields.reason ?? confirmation.fields.reason ?? COPY.defaultReason;
  const [itemName, setItemName] = useState(toInputValue(draftFields.item_name));
  const [quantity, setQuantity] = useState(toInputValue(draftFields.stock_out_quantity));
  const [reason, setReason] = useState(toInputValue(reasonSeed));
  const [isResolved, setIsResolved] = useState(false);
  const approveMutation = useApproveConfirmationMutation();
  const rejectMutation = useRejectConfirmationMutation();
  const error = approveMutation.error ?? rejectMutation.error;
  const isSubmitting = approveMutation.isSubmitting || rejectMutation.isSubmitting;

  useEffect(() => {
    setItemName(toInputValue(draftFields.item_name));
    setQuantity(toInputValue(draftFields.stock_out_quantity));
    setReason(toInputValue(reasonSeed));
  }, [confirmation.confirmation_id, draftFieldsSyncKey, reasonSeed]);

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
      <AppTextField
        label={COPY.reason}
        placeholder={COPY.reason}
        value={reason}
        onChangeText={setReason}
      />
    </ConfirmationCardShell>
  );
}
