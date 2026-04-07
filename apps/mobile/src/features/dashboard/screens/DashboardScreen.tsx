import { useEffect } from "react";
import { ScrollView, StyleSheet, View } from "react-native";

import { DashboardExceptionCard } from "../components/DashboardExceptionCard";
import { DashboardQuickActions } from "../components/DashboardQuickActions";
import { DashboardSummaryHero } from "../components/DashboardSummaryHero";
import { useDemoBootstrapMutation } from "../hooks/useDemoBootstrapMutation";
import { useDashboardSummaryQuery } from "../hooks/useDashboardSummaryQuery";
import { useLowStockAlertsQuery } from "../hooks/useLowStockAlertsQuery";
import { usePendingConfirmationsQuery } from "../hooks/usePendingConfirmationsQuery";
import { getFriendlyStatusMessage } from "../../../shared/copy/getFriendlyStatusMessage";
import { useSessionStream } from "../../../shared/session/useSessionStream";
import { AppScreen, DebugDisclosure, EmptyState, InlineNotice, PrimaryButton, space } from "../../../shared/ui";

type DashboardScreenProps = {
  navigation?: {
    navigate: (screenName: string) => void;
  };
};

const CONFIRMATION_LABELS: Record<string, string> = {
  "voice-stock-in": "语音入库确认",
  "receipt-stock-in-batch": "票据入库确认",
  "stock-out": "出库确认",
};

function getConfirmationTitle(confirmationType: string) {
  return CONFIRMATION_LABELS[confirmationType] ?? confirmationType;
}

const SCREEN_TITLE = "今日门店概览";
const SCREEN_SUBTITLE = "聚焦门店库存与待处理事项，先看风险，再安排动作。";

export default function DashboardScreen({ navigation }: DashboardScreenProps) {
  const summary = useDashboardSummaryQuery();
  const alerts = useLowStockAlertsQuery();
  const pendingConfirmations = usePendingConfirmationsQuery();
  const demoBootstrap = useDemoBootstrapMutation();
  const sessionStream = useSessionStream();

  function refreshDashboard() {
    summary.refresh();
    alerts.refresh();
    pendingConfirmations.refresh();
  }

  useEffect(() => {
    const eventType = sessionStream.lastEvent?.event_type;
    if (
      eventType !== "inventory.updated"
      && eventType !== "alert.updated"
      && eventType !== "confirmation.created"
      && eventType !== "confirmation.resolved"
    ) {
      return;
    }
    refreshDashboard();
  }, [sessionStream.lastEvent?.event_id]);

  useEffect(() => {
    if (sessionStream.dataResetVersion === 0) {
      return;
    }
    refreshDashboard();
  }, [sessionStream.dataResetVersion]);

  function handleNavigateToWorkbench() {
    navigation?.navigate("工作台");
  }

  async function handleDemoReset() {
    const result = await demoBootstrap.runDemoBootstrap();
    if (result === null) {
      return;
    }
    sessionStream.notifyDemoDataReset();
  }

  if (summary.isLoading || alerts.isLoading || pendingConfirmations.isLoading) {
    return (
      <AppScreen title={SCREEN_TITLE} subtitle={SCREEN_SUBTITLE}>
        <EmptyState
          title="正在同步今日门店概览"
          description="请稍候，我们正在整理最新库存与待处理事项。"
        />
      </AppScreen>
    );
  }

  if (summary.error || alerts.error || pendingConfirmations.error || summary.data === null) {
    return (
      <AppScreen title={SCREEN_TITLE} subtitle={SCREEN_SUBTITLE}>
        <InlineNotice
          tone="error"
          title="今日概览暂时不可用"
          message={getFriendlyStatusMessage(
            summary.error ?? alerts.error ?? pendingConfirmations.error,
            "请稍后再试。",
          )}
        />
      </AppScreen>
    );
  }

  const lowStockItems = alerts.data.map((alert) => ({
    id: alert.alert_id,
    title: alert.item_name,
    detail: `库存 ${alert.stock} / 阈值 ${alert.threshold} ${alert.unit}`,
    badgeTone: "warning" as const,
    badgeLabel: "低库存",
  }));

  const pendingItems = pendingConfirmations.data.map((confirmation) => ({
    id: confirmation.confirmation_id,
    title: getConfirmationTitle(confirmation.confirmation_type),
    detail: confirmation.fields.summary ?? "等待门店确认处理。",
    badgeTone: "neutral" as const,
    badgeLabel: "待确认",
  }));

  return (
    <AppScreen title={SCREEN_TITLE} subtitle={SCREEN_SUBTITLE}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <DashboardSummaryHero summary={summary.data} />
        <DashboardQuickActions onNavigateToWorkbench={handleNavigateToWorkbench} />
        <DashboardExceptionCard
          title="低库存提醒"
          subtitle="优先处理即将断货的商品，减少缺货影响。"
          emptyTitle="库存状态平稳"
          emptyDescription="当前没有低库存预警。"
          items={lowStockItems}
        />
        <DashboardExceptionCard
          title="待处理确认"
          subtitle="集中处理语音、票据与库存确认请求。"
          emptyTitle="确认队列已清空"
          emptyDescription="暂无待处理确认。"
          items={pendingItems}
        />
        <DebugDisclosure title="调试工具">
          <View style={styles.debugPanel}>
            <PrimaryButton
              label="重置演示数据"
              loading={demoBootstrap.isSubmitting}
              loadingLabel="重置中..."
              onPress={() => {
                void handleDemoReset();
              }}
            />
            {demoBootstrap.successMessage ? (
              <InlineNotice tone="success" message={demoBootstrap.successMessage} />
            ) : null}
            {demoBootstrap.error ? (
              <InlineNotice tone="error" title="重置失败" message={demoBootstrap.error} />
            ) : null}
          </View>
        </DebugDisclosure>
      </ScrollView>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: space.s12,
    paddingBottom: space.s24,
  },
  debugPanel: {
    gap: space.s12,
  },
});
