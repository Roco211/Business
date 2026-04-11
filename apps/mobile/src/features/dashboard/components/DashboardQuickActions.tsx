import { Pressable, StyleSheet, Text, View } from "react-native";

import { WORKBENCH_INTENT_COPY, type WorkbenchIntent } from "../../chat/workbenchIntent";
import { SectionHeader, SurfaceCard, color, radius, space } from "../../../shared/ui";

type DashboardQuickActionsProps = {
  onNavigateToWorkbench: (intent: WorkbenchIntent) => void;
};

const QUICK_ACTIONS: WorkbenchIntent[] = [
  "voice-query",
  "photo-stock-in",
  "receipt-entry",
  "pending-confirmations",
];

export function DashboardQuickActions({ onNavigateToWorkbench }: DashboardQuickActionsProps) {
  return (
    <SurfaceCard emphasis="outlined" style={styles.shell}>
      <SectionHeader title="常用操作" subtitle="从语音、拍照和票据入口继续处理门店任务。" />
      <View style={styles.actions}>
        {QUICK_ACTIONS.map((intent) => (
          <Pressable
            key={intent}
            accessibilityRole="button"
            onPress={() => onNavigateToWorkbench(intent)}
            style={styles.actionButton}
          >
            <Text style={styles.actionLabel}>{WORKBENCH_INTENT_COPY[intent].dashboardLabel}</Text>
            <Text style={styles.actionDetail}>{WORKBENCH_INTENT_COPY[intent].dashboardDetail}</Text>
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
