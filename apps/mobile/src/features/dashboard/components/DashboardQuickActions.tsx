import { StyleSheet, View } from "react-native";

import { PillActionButton, SectionHeader, SurfaceCard, space } from "../../../shared/ui";

type DashboardQuickActionsProps = {
  onNavigateToWorkbench: () => void;
};

const QUICK_ACTIONS = [
  { key: "voice-inventory", label: "语音查货" },
  { key: "photo-stock-in", label: "拍照入库" },
  { key: "receipt-ocr", label: "票据识别" },
  { key: "pending-confirmations", label: "待确认" },
] as const;

export function DashboardQuickActions({ onNavigateToWorkbench }: DashboardQuickActionsProps) {
  return (
    <SurfaceCard emphasis="outlined">
      <SectionHeader title="快捷操作" subtitle="统一跳转到工作台，继续处理具体任务。" />
      <View style={styles.actions}>
        {QUICK_ACTIONS.map((action) => (
          <PillActionButton
            key={action.key}
            label={action.label}
            onPress={onNavigateToWorkbench}
            style={styles.actionButton}
          />
        ))}
      </View>
    </SurfaceCard>
  );
}

const styles = StyleSheet.create({
  actions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: space.s8,
    marginTop: space.s12,
  },
  actionButton: {
    flexGrow: 1,
    minWidth: "48%",
  },
});
