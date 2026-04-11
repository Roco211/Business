import { StyleSheet, Text, View } from "react-native";

import type { DashboardSummaryRecord } from "../hooks/useDashboardSummaryQuery";
import { SectionHeader, SurfaceCard, color, radius, space } from "../../../shared/ui";

type DashboardSummaryHeroProps = {
  summary: DashboardSummaryRecord;
};

export function DashboardSummaryHero({ summary }: DashboardSummaryHeroProps) {
  const metrics = [
    { key: "today-stock-in", label: "今日入库", value: summary.today_stock_in_count },
    { key: "tasks-completed", label: "已完成任务", value: summary.today_task_completed_count },
    { key: "pending-confirmations", label: "待处理确认", value: summary.pending_confirmations_count },
    { key: "low-stock-alerts", label: "低库存提醒", value: summary.open_low_stock_alert_count },
  ];

  return (
    <SurfaceCard emphasis="elevated" style={styles.hero}>
      <Text style={styles.eyebrow}>今天先看店铺概览</Text>
      <SectionHeader title="店铺概览" subtitle="先看经营状态，再安排今天的处理顺序。" />
      <View style={styles.metrics}>
        {metrics.map((metric) => (
          <View key={metric.key} style={styles.metricItem}>
            <Text style={styles.metricLabel}>{metric.label}</Text>
            <Text style={styles.metricValue}>{metric.value}</Text>
          </View>
        ))}
      </View>
    </SurfaceCard>
  );
}

const styles = StyleSheet.create({
  hero: {
    gap: space.s12,
  },
  eyebrow: {
    color: color.accentPrimary,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.4,
  },
  metrics: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: space.s8,
  },
  metricItem: {
    backgroundColor: "rgba(255, 255, 255, 0.76)",
    borderColor: "rgba(45, 33, 28, 0.06)",
    borderRadius: radius.card,
    borderWidth: 1,
    flexGrow: 1,
    minWidth: "48%",
    paddingHorizontal: space.s16,
    paddingVertical: space.s16,
  },
  metricLabel: {
    color: color.fgSecondary,
    fontSize: 13,
  },
  metricValue: {
    color: color.fgPrimary,
    fontSize: 28,
    fontWeight: "700",
    marginTop: space.s8,
  },
});
