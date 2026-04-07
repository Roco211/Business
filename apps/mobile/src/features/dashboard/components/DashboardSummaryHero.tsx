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
    <SurfaceCard emphasis="elevated">
      <SectionHeader title="今日概览" subtitle="四项核心指标帮助你快速判断门店状态。" />
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
  metrics: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: space.s8,
    marginTop: space.s12,
  },
  metricItem: {
    backgroundColor: color.bgApp,
    borderColor: color.borderSubtle,
    borderRadius: radius.card,
    borderWidth: 1,
    flexGrow: 1,
    minWidth: "48%",
    paddingHorizontal: space.s12,
    paddingVertical: space.s12,
  },
  metricLabel: {
    color: color.fgSecondary,
    fontSize: 13,
  },
  metricValue: {
    color: color.fgPrimary,
    fontSize: 24,
    fontWeight: "700",
    marginTop: space.s8,
  },
});
