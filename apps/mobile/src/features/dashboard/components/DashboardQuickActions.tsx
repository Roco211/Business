import { StyleSheet, View } from "react-native";

import { WORKBENCH_INTENT_COPY, type WorkbenchIntent } from "../../chat/workbenchIntent";
import { PillActionButton, SectionHeader, SurfaceCard, space } from "../../../shared/ui";

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
    <SurfaceCard emphasis="outlined">
      <SectionHeader title="快捷操作" subtitle="统一跳转到工作台，继续处理具体任务。" />
      <View style={styles.actions}>
        {QUICK_ACTIONS.map((intent) => (
          <PillActionButton
            key={intent}
            label={WORKBENCH_INTENT_COPY[intent].dashboardLabel}
            onPress={() => onNavigateToWorkbench(intent)}
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
