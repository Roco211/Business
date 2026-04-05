import { useEffect } from "react";
import { Button, ScrollView, Text, View } from "react-native";

import { useDemoBootstrapMutation } from "../hooks/useDemoBootstrapMutation";
import { useDashboardSummaryQuery } from "../hooks/useDashboardSummaryQuery";
import { useLowStockAlertsQuery } from "../hooks/useLowStockAlertsQuery";
import { usePendingConfirmationsQuery } from "../hooks/usePendingConfirmationsQuery";
import { useSessionStream } from "../../../shared/session/useSessionStream";


export default function DashboardScreen() {
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

  async function handleDemoReset() {
    const result = await demoBootstrap.runDemoBootstrap();
    if (result === null) {
      return;
    }
    sessionStream.notifyDemoDataReset();
  }

  if (summary.isLoading || alerts.isLoading || pendingConfirmations.isLoading) {
    return (
      <View>
        <Text>Loading dashboard...</Text>
      </View>
    );
  }

  if (summary.error || alerts.error || pendingConfirmations.error || summary.data === null) {
    return (
      <View>
        <Text>Dashboard unavailable</Text>
        <Text>{summary.error ?? alerts.error ?? pendingConfirmations.error ?? "Unknown error"}</Text>
      </View>
    );
  }

  return (
    <ScrollView>
      <Text>Dashboard</Text>
      <Button
        title={demoBootstrap.isSubmitting ? "Resetting Demo..." : "Reset Demo State"}
        onPress={() => {
          void handleDemoReset();
        }}
        disabled={demoBootstrap.isSubmitting}
      />
      {demoBootstrap.successMessage ? <Text>{demoBootstrap.successMessage}</Text> : null}
      {demoBootstrap.error ? <Text>{demoBootstrap.error}</Text> : null}

      <Text>{`Today stock-in: ${summary.data.today_stock_in_count}`}</Text>
      <Text>{`Completed tasks: ${summary.data.today_task_completed_count}`}</Text>
      <Text>{`Pending confirmations: ${summary.data.pending_confirmations_count}`}</Text>
      <Text>{`Open low-stock alerts: ${summary.data.open_low_stock_alert_count}`}</Text>

      <Text>Low-stock alerts</Text>
      {alerts.data.length === 0 ? <Text>No open low-stock alerts.</Text> : null}
      {alerts.data.map((alert) => (
        <View key={alert.alert_id}>
          <Text>{alert.item_name}</Text>
          <Text>{`${alert.stock} / ${alert.threshold} ${alert.unit}`}</Text>
        </View>
      ))}

      <Text>Pending confirmations</Text>
      {pendingConfirmations.data.length === 0 ? <Text>No pending confirmations.</Text> : null}
      {pendingConfirmations.data.map((confirmation) => (
        <View key={confirmation.confirmation_id}>
          <Text>{confirmation.confirmation_type}</Text>
          <Text>{confirmation.fields.summary ?? "Confirmation pending"}</Text>
        </View>
      ))}
    </ScrollView>
  );
}
