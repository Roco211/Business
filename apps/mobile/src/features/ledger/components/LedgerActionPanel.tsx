import { StyleSheet, Text, View } from "react-native";

import type { InventoryItemRecord } from "../hooks/useInventoryItemsQuery";
import { AppTextField, EmptyState, InlineNotice, PillActionButton, PrimaryButton, SurfaceCard } from "../../../shared/ui";
import { color, space } from "../../../shared/ui/tokens";

export type LedgerActionType = "correction" | "stock-out";

type LedgerActionPanelProps = {
  selectedItem: InventoryItemRecord | null;
  selectedAction: LedgerActionType | null;
  correctedQuantity: string;
  correctionReason: string;
  stockOutQuantity: string;
  stockOutReason: string;
  correctionError: string | null;
  stockOutError: string | null;
  correctionSubmitting: boolean;
  stockOutSubmitting: boolean;
  onSelectAction: (action: LedgerActionType) => void;
  onChangeCorrectedQuantity: (value: string) => void;
  onChangeCorrectionReason: (value: string) => void;
  onChangeStockOutQuantity: (value: string) => void;
  onChangeStockOutReason: (value: string) => void;
  onSubmitCorrection: () => void;
  onSubmitStockOut: () => void;
};

export function LedgerActionPanel({
  selectedItem,
  selectedAction,
  correctedQuantity,
  correctionReason,
  stockOutQuantity,
  stockOutReason,
  correctionError,
  stockOutError,
  correctionSubmitting,
  stockOutSubmitting,
  onSelectAction,
  onChangeCorrectedQuantity,
  onChangeCorrectionReason,
  onChangeStockOutQuantity,
  onChangeStockOutReason,
  onSubmitCorrection,
  onSubmitStockOut,
}: LedgerActionPanelProps) {
  return (
    <View testID="ledger-action-panel">
      <SurfaceCard emphasis="outlined">
        {!selectedItem ? (
          <EmptyState title="先选择库存项" description="从上方库存卡片选择“库存修正”或“出库登记”后开始处理。" />
        ) : (
          <View style={styles.content}>
            <Text style={styles.itemName}>{selectedItem.name}</Text>
            <Text style={styles.itemStock}>{`当前库存 ${selectedItem.current_stock} ${selectedItem.default_unit}`}</Text>

            <View style={styles.actionSwitches}>
              <PillActionButton label="库存修正" onPress={() => onSelectAction("correction")} />
              <PillActionButton label="出库登记" onPress={() => onSelectAction("stock-out")} />
            </View>

            {selectedAction === "correction" ? (
              <View style={styles.form}>
                <AppTextField
                  label="修正后库存"
                  testID="ledger-correction-quantity-input"
                  value={correctedQuantity}
                  keyboardType="numeric"
                  onChangeText={onChangeCorrectedQuantity}
                />
                <AppTextField
                  label="修正原因"
                  testID="ledger-correction-reason-input"
                  value={correctionReason}
                  onChangeText={onChangeCorrectionReason}
                />
                {correctionError ? (
                  <InlineNotice tone="error" title="提交失败" message={correctionError} />
                ) : null}
                <PrimaryButton
                  label="提交库存修正"
                  loadingLabel="提交中..."
                  testID="ledger-action-submit-button"
                  loading={correctionSubmitting}
                  onPress={onSubmitCorrection}
                />
              </View>
            ) : null}

            {selectedAction === "stock-out" ? (
              <View style={styles.form}>
                <AppTextField
                  label="出库数量"
                  testID="ledger-stock-out-quantity-input"
                  value={stockOutQuantity}
                  keyboardType="numeric"
                  onChangeText={onChangeStockOutQuantity}
                />
                <AppTextField
                  label="出库原因"
                  testID="ledger-stock-out-reason-input"
                  value={stockOutReason}
                  onChangeText={onChangeStockOutReason}
                />
                {stockOutError ? (
                  <InlineNotice tone="error" title="提交失败" message={stockOutError} />
                ) : null}
                <PrimaryButton
                  label="提交出库登记"
                  loadingLabel="提交中..."
                  testID="ledger-action-submit-button"
                  loading={stockOutSubmitting}
                  onPress={onSubmitStockOut}
                />
              </View>
            ) : null}
          </View>
        )}
      </SurfaceCard>
    </View>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: space.s12,
  },
  itemName: {
    color: color.fgPrimary,
    fontSize: 18,
    fontWeight: "600",
  },
  itemStock: {
    color: color.fgSecondary,
    fontSize: 14,
  },
  actionSwitches: {
    flexDirection: "row",
    gap: space.s8,
  },
  form: {
    gap: space.s12,
  },
});
