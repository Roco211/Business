import { Pressable, StyleSheet, Text, View } from "react-native";

import { SectionHeader, SurfaceCard, color, radius, space } from "../../../shared/ui";

type DashboardQuickActionsProps = {
  onNavigateToWorkbench: () => void;
};

const QUICK_ACTIONS = [
  { key: "voice-inventory", label: "语音查货", detail: "一句话查看库存和缺货风险" },
  { key: "photo-stock-in", label: "拍照入库", detail: "对着商品拍照后继续确认" },
  { key: "receipt-ocr", label: "票据识别", detail: "快速整理票据条目和金额" },
  { key: "pending-confirmations", label: "待处理确认", detail: "集中处理待复核事项" },
] as const;

export function DashboardQuickActions({ onNavigateToWorkbench }: DashboardQuickActionsProps) {
  return (
    <SurfaceCard emphasis="outlined" style={styles.shell}>
      <SectionHeader title="常用操作" subtitle="从语音、拍照和票据入口继续处理门店任务。" />
      <View style={styles.actions}>
        {QUICK_ACTIONS.map((action) => (
          <Pressable
            key={action.key}
            accessibilityRole="button"
            onPress={onNavigateToWorkbench}
            style={styles.actionButton}
          >
            <Text style={styles.actionLabel}>{action.label}</Text>
            <Text style={styles.actionDetail}>{action.detail}</Text>
          </Pressable>
        ))}
      </View>
    </SurfaceCard>
  );
}

const styles = StyleSheet.create({
  shell: {
    gap: space.s12,
  },
  actions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: space.s8,
  },
  actionButton: {
    backgroundColor: "rgba(255, 255, 255, 0.8)",
    borderColor: "rgba(45, 33, 28, 0.06)",
    borderRadius: radius.card,
    borderWidth: 1,
    flexGrow: 1,
    minWidth: "48%",
    paddingHorizontal: space.s12,
    paddingVertical: space.s12,
  },
  actionLabel: {
    color: color.fgPrimary,
    fontSize: 15,
    fontWeight: "600",
  },
  actionDetail: {
    color: color.fgSecondary,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 4,
  },
});
