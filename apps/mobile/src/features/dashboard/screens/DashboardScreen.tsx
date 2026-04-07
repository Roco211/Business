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
import {
  AppScreen,
  DebugDisclosure,
  EmptyState,
  InlineNotice,
  PrimaryButton,
  SectionHeader,
  SurfaceCard,
  space,
} from "../../../shared/ui";

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

const SCREEN_TITLE = "今日门店总览";
const SCREEN_SUBTITLE = "聚焦门店库存与待处理事项，先看风险，再安排动作。";

type HealthTone = "neutral" | "warning" | "error" | "success";

function getConfirmationTitle(confirmationType: string) {
  return CONFIRMATION_LABELS[confirmationType] ?? confirmationType;
}

function getConnectionHealth(connectionState: string, bootstrapError: string | null) {
  if (connectionState === "connected") {
    return {
      tone: "success" as HealthTone,
      title: "连接状态：已连接",
      message: "实时同步正常，可继续处理门店任务。",
    };
  }

  if (connectionState === "connecting" || connectionState === "bootstrapping") {
    return {
      tone: "warning" as HealthTone,
      title: "连接状态：正在重连",
      message: "正在恢复实时同步，请稍候。",
    };
  }

  if (connectionState === "disconnected") {
    return {
      tone: "warning" as HealthTone,
      title: "连接状态：连接中断",
      message: "已切换到手动刷新模式，请留意网络。",
    };
  }

  if (connectionState === "error") {
    return {
      tone: "error" as HealthTone,
      title: "连接状态：服务异常",
      message: getFriendlyStatusMessage(bootstrapError, "实时连接异常，请检查网络后重试。"),
    };
  }

  return {
    tone: "neutral" as HealthTone,
    title: "连接状态：待连接",
    message: "正在准备会话连接。",
  };
}

function getNextActionCopy(pendingCount: number, alertCount: number) {
  if (pendingCount > 0 || alertCount > 0) {
    return "下一步：前往工作台处理待确认与补货任务。";
  }

  return "下一步：前往工作台完成日常巡检。";
}

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
          title="正在同步今日门店总览"
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
          title="今日总览暂不可用"
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

  const connectionHealth = getConnectionHealth(sessionStream.connectionState, sessionStream.bootstrapError);
  const nextActionCopy = getNextActionCopy(
    summary.data.pending_confirmations_count,
    summary.data.open_low_stock_alert_count,
  );

  return (
    <AppScreen title={SCREEN_TITLE} subtitle={SCREEN_SUBTITLE}>
      <ScrollView contentContainerStyle={styles.content} showsVerticalScrollIndicator={false}>
        <DashboardSummaryHero summary={summary.data} />
        <DashboardQuickActions onNavigateToWorkbench={handleNavigateToWorkbench} />
        <SurfaceCard emphasis="outlined" style={styles.healthCard}>
          <SectionHeader title="当前健康" subtitle="先看连接状态，再安排下一步动作。" />
          <InlineNotice tone={connectionHealth.tone} title={connectionHealth.title} message={connectionHealth.message} />
          <InlineNotice
            tone="neutral"
            title={nextActionCopy}
            message="调试工具保留在下方，排障时再展开即可。"
          />
        </SurfaceCard>
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
  healthCard: {
    gap: space.s12,
  },
  debugPanel: {
    gap: space.s12,
  },
});
