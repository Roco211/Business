import { useEffect, useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";

import { AuditTimeline } from "../components/AuditTimeline";
import { InventoryItemCard } from "../components/InventoryItemCard";
import { LedgerActionPanel, type LedgerActionType } from "../components/LedgerActionPanel";
import { useAuditLogsQuery } from "../hooks/useAuditLogsQuery";
import { useCreateCorrectionMutation } from "../hooks/useCreateCorrectionMutation";
import { useCreateStockOutMutation } from "../hooks/useCreateStockOutMutation";
import { useInventoryItemsQuery, type InventoryItemRecord } from "../hooks/useInventoryItemsQuery";
import {
  AppScreen,
  AppTextField,
  EmptyState,
  InlineNotice,
  SectionHeader,
  SurfaceCard,
} from "../../../shared/ui";
import { useSessionStream } from "../../../shared/session/useSessionStream";
import { space } from "../../../shared/ui/tokens";


function formatEditableQuantity(quantity: string) {
  return quantity.replace(/\.0+$/, "").replace(/(\.\d*?)0+$/, "$1");
}


export default function LedgerScreen() {
  const [searchText, setSearchText] = useState("");
  const [selectedAction, setSelectedAction] = useState<LedgerActionType | null>(null);
  const [selectedItem, setSelectedItem] = useState<InventoryItemRecord | null>(null);
  const [selectedItemCurrentStock, setSelectedItemCurrentStock] = useState("");
  const [correctedQuantity, setCorrectedQuantity] = useState("");
  const [correctionReason, setCorrectionReason] = useState("");
  const [stockOutQuantity, setStockOutQuantity] = useState("");
  const [stockOutReason, setStockOutReason] = useState("");

  const inventory = useInventoryItemsQuery(searchText);
  const auditLogs = useAuditLogsQuery();
  const correction = useCreateCorrectionMutation();
  const stockOut = useCreateStockOutMutation();
  const sessionStream = useSessionStream();

  useEffect(() => {
    const eventType = sessionStream.lastEvent?.event_type;
    if (eventType !== "inventory.updated" && eventType !== "confirmation.resolved") {
      return;
    }
    inventory.refresh();
    auditLogs.refresh();
  }, [sessionStream.lastEvent?.event_id]);

  useEffect(() => {
    if (sessionStream.dataResetVersion === 0) {
      return;
    }
    inventory.refresh();
    auditLogs.refresh();
  }, [sessionStream.dataResetVersion]);

  async function handleSubmitCorrection() {
    if (!selectedItem) {
      return;
    }
    const result = await correction.submitCorrection({
      item_id: selectedItem.item_id,
      expected_quantity: Number(selectedItemCurrentStock),
      corrected_quantity: Number(correctedQuantity),
      reason: correctionReason,
    });
    if (result === null) {
      return;
    }
    setCorrectedQuantity("");
    setCorrectionReason("");
    setSelectedAction(null);
    setSelectedItem(null);
    setSelectedItemCurrentStock("");
    inventory.refresh();
    auditLogs.refresh();
  }

  async function handleSubmitStockOut() {
    if (!selectedItem) {
      return;
    }
    const result = await stockOut.submitStockOut({
      item_id: selectedItem.item_id,
      expected_quantity: Number(selectedItemCurrentStock),
      stock_out_quantity: Number(stockOutQuantity),
      reason: stockOutReason,
    });
    if (result === null) {
      return;
    }
    setStockOutQuantity("");
    setStockOutReason("");
    setSelectedAction(null);
    setSelectedItem(null);
    setSelectedItemCurrentStock("");
    inventory.refresh();
    auditLogs.refresh();
  }

  if (inventory.isLoading || auditLogs.isLoading) {
    return (
      <AppScreen title="库存台账" subtitle="轻量库存工作区">
        <View testID="ledger-loading-state">
          <SurfaceCard emphasis="outlined">
            <InlineNotice tone="neutral" title="同步中" message="正在拉取库存与最近活动，请稍候。" />
          </SurfaceCard>
        </View>
      </AppScreen>
    );
  }

  if (inventory.error || auditLogs.error) {
    return (
      <AppScreen title="库存台账" subtitle="轻量库存工作区">
        <View testID="ledger-error-state">
          <SurfaceCard emphasis="outlined">
            <InlineNotice
              tone="error"
              title="台账暂时不可用"
              message={inventory.error ?? auditLogs.error ?? "请稍后重试"}
            />
          </SurfaceCard>
        </View>
      </AppScreen>
    );
  }

  return (
    <AppScreen title="库存台账" subtitle="轻量库存工作区">
      <ScrollView contentContainerStyle={styles.scrollBody}>
        <SurfaceCard emphasis="outlined">
          <SectionHeader title="搜索" subtitle="输入商品名快速过滤库存卡片" />
          <AppTextField
            label="搜索库存"
            testID="ledger-search-input"
            placeholder="例如：苹果、可乐"
            value={searchText}
            onChangeText={setSearchText}
          />
        </SurfaceCard>

        <SectionHeader title="库存工作区" subtitle="从卡片直接进入修正或出库操作。" />
        {inventory.data.length === 0 ? (
          <EmptyState title="暂无匹配库存" description="请调整搜索条件，或稍后刷新数据。" />
        ) : (
          <View style={styles.cards}>
            {inventory.data.map((item) => (
              <InventoryItemCard
                key={item.item_id}
                item={item}
                onPressCorrection={() => {
                  setSelectedAction("correction");
                  setSelectedItem(item);
                  setSelectedItemCurrentStock(item.current_stock);
                  setCorrectedQuantity(formatEditableQuantity(item.current_stock));
                  setCorrectionReason("");
                }}
                onPressStockOut={() => {
                  setSelectedAction("stock-out");
                  setSelectedItem(item);
                  setSelectedItemCurrentStock(item.current_stock);
                  setStockOutQuantity("");
                  setStockOutReason("");
                }}
              />
            ))}
          </View>
        )}

        <SectionHeader title="操作面板" subtitle="在这里提交库存修正或出库登记。" />
        <LedgerActionPanel
          selectedItem={selectedItem}
          selectedAction={selectedAction}
          correctedQuantity={correctedQuantity}
          correctionReason={correctionReason}
          stockOutQuantity={stockOutQuantity}
          stockOutReason={stockOutReason}
          correctionError={correction.error}
          stockOutError={stockOut.error}
          correctionSubmitting={correction.isSubmitting}
          stockOutSubmitting={stockOut.isSubmitting}
          onSelectAction={(action) => {
            setSelectedAction(action);
          }}
          onChangeCorrectedQuantity={setCorrectedQuantity}
          onChangeCorrectionReason={setCorrectionReason}
          onChangeStockOutQuantity={setStockOutQuantity}
          onChangeStockOutReason={setStockOutReason}
          onSubmitCorrection={() => {
            void handleSubmitCorrection();
          }}
          onSubmitStockOut={() => {
            void handleSubmitStockOut();
          }}
        />

        <SectionHeader title="最近活动" subtitle="按时间查看库存相关操作记录。" />
        <AuditTimeline logs={auditLogs.data} />
      </ScrollView>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  scrollBody: {
    gap: space.s12,
    paddingBottom: space.s16,
  },
  cards: {
    gap: space.s8,
  },
});
