import { useEffect, useRef, useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";

import { AuditTimeline } from "../components/AuditTimeline";
import { InventoryItemCard } from "../components/InventoryItemCard";
import { LedgerActionPanel, type LedgerActionType } from "../components/LedgerActionPanel";
import { useAuditLogsQuery } from "../hooks/useAuditLogsQuery";
import { useCreateCorrectionMutation } from "../hooks/useCreateCorrectionMutation";
import { useCreateStockOutMutation } from "../hooks/useCreateStockOutMutation";
import { useInventoryItemsQuery, type InventoryItemRecord } from "../hooks/useInventoryItemsQuery";
import { getFriendlyStatusMessage } from "../../../shared/copy/getFriendlyStatusMessage";
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
  const scrollViewRef = useRef<ScrollView | null>(null);
  const actionPanelOffsetRef = useRef(0);

  const inventory = useInventoryItemsQuery(searchText);
  const auditLogs = useAuditLogsQuery();
  const correction = useCreateCorrectionMutation();
  const stockOut = useCreateStockOutMutation();
  const sessionStream = useSessionStream();
  const [hasCompletedInitialLoad, setHasCompletedInitialLoad] = useState(
    () => !inventory.isLoading && !auditLogs.isLoading,
  );

  useEffect(() => {
    if (!hasCompletedInitialLoad && !inventory.isLoading && !auditLogs.isLoading) {
      setHasCompletedInitialLoad(true);
    }
  }, [hasCompletedInitialLoad, inventory.isLoading, auditLogs.isLoading]);

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

  useEffect(() => {
    if (!selectedItem) {
      return;
    }

    const refreshedSelectedItem = inventory.data.find((item) => item.item_id === selectedItem.item_id);
    if (!refreshedSelectedItem) {
      return;
    }

    if (refreshedSelectedItem !== selectedItem) {
      setSelectedItem(refreshedSelectedItem);
    }

    if (refreshedSelectedItem.current_stock !== selectedItemCurrentStock) {
      setSelectedItemCurrentStock(refreshedSelectedItem.current_stock);
    }
  }, [inventory.data, selectedItem, selectedItemCurrentStock]);

  function revealActionPanel() {
    const scrollToPanel = () => {
      scrollViewRef.current?.scrollTo({
        y: Math.max(actionPanelOffsetRef.current - space.s12, 0),
        animated: true,
      });
    };

    if (typeof requestAnimationFrame === "function") {
      requestAnimationFrame(scrollToPanel);
      return;
    }

    setTimeout(scrollToPanel, 0);
  }

  function switchActionForItem(item: InventoryItemRecord, action: LedgerActionType) {
    setSelectedItem(item);
    setSelectedAction(action);
    setSelectedItemCurrentStock(item.current_stock);

    if (action === "correction") {
      setCorrectedQuantity(formatEditableQuantity(item.current_stock));
      setCorrectionReason("");
      setStockOutQuantity("");
      setStockOutReason("");
    } else {
      setStockOutQuantity("");
      setStockOutReason("");
      setCorrectedQuantity("");
      setCorrectionReason("");
    }

    revealActionPanel();
  }

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

  const isInitialLoading = !hasCompletedInitialLoad && (inventory.isLoading || auditLogs.isLoading);

  if (isInitialLoading) {
    return (
      <AppScreen title="库存台账" subtitle="轻量库存工作区">
        <View testID="ledger-loading-state">
          <EmptyState title="正在同步库存台账" description="请稍候，我们正在整理库存与最近活动。" />
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
              title="库存台账暂时不可用"
              message={getFriendlyStatusMessage(inventory.error ?? auditLogs.error, "请稍后再试。")}
            />
          </SurfaceCard>
        </View>
      </AppScreen>
    );
  }

  return (
    <AppScreen title="库存台账" subtitle="轻量库存工作区">
      <ScrollView ref={scrollViewRef} contentContainerStyle={styles.scrollBody}>
        <SurfaceCard emphasis="outlined">
          <SectionHeader title="搜索与筛选" subtitle="输入商品名称，快速定位需要处理的库存条目。" />
          <AppTextField
            label="搜索库存"
            testID="ledger-search-input"
            placeholder="例如：苹果、可乐"
            value={searchText}
            onChangeText={setSearchText}
          />
        </SurfaceCard>

        <SectionHeader title="库存工作区" subtitle="从库存卡片可直接发起修正或出库登记。" />
        {inventory.data.length === 0 ? (
          <EmptyState title="暂未找到匹配商品" description="试试更换关键词，或稍后再刷新库存数据。" />
        ) : (
          <View style={styles.cards}>
            {inventory.data.map((item) => (
              <InventoryItemCard
                key={item.item_id}
                item={item}
                onPressCorrection={() => {
                  switchActionForItem(item, "correction");
                }}
                onPressStockOut={() => {
                  switchActionForItem(item, "stock-out");
                }}
              />
            ))}
          </View>
        )}

        <View
          testID="ledger-action-panel-section"
          style={styles.actionPanelSection}
          onLayout={(event) => {
            actionPanelOffsetRef.current = event.nativeEvent.layout.y;
          }}
        >
          <SectionHeader title="操作面板" subtitle="确认数量与原因后，在此提交库存修正或出库登记。" />
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
              if (!selectedItem) {
                return;
              }
              switchActionForItem(selectedItem, action);
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
        </View>

        <SectionHeader title="活动时间线" subtitle="按时间顺序查看最近库存相关操作记录。" />
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
  actionPanelSection: {
    gap: space.s12,
  },
});
