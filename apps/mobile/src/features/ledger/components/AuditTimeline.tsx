import { StyleSheet, Text, View } from "react-native";

import type { AuditLogRecord } from "../hooks/useAuditLogsQuery";
import { EmptyState, SurfaceCard } from "../../../shared/ui";
import { color, space } from "../../../shared/ui/tokens";

type AuditTimelineProps = {
  logs: AuditLogRecord[];
};

function formatAuditLine(itemName: string | undefined, quantityDelta: number | undefined) {
  if (!itemName) {
    return "库存有更新";
  }
  if (typeof quantityDelta !== "number") {
    return itemName;
  }
  if (quantityDelta > 0) {
    return `${itemName} +${quantityDelta}`;
  }
  return `${itemName} ${quantityDelta}`;
}

export function AuditTimeline({ logs }: AuditTimelineProps) {
  if (logs.length === 0) {
    return <EmptyState title="最近活动为空" description="当前还没有新的库存活动记录。" />;
  }

  return (
    <View style={styles.container}>
      {logs.map((log) => (
        <View key={log.audit_log_id} testID={`audit-timeline-item-${log.audit_log_id}`}>
          <SurfaceCard tone="muted" emphasis="outlined">
            <Text style={styles.action}>{log.action}</Text>
            <Text style={styles.summary}>{formatAuditLine(log.metadata.item_name, log.metadata.quantity_delta)}</Text>
            <Text style={styles.time}>{log.created_at}</Text>
          </SurfaceCard>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: space.s8,
  },
  action: {
    color: color.fgPrimary,
    fontSize: 14,
    fontWeight: "600",
  },
  summary: {
    color: color.fgPrimary,
    fontSize: 15,
    marginTop: space.s8,
  },
  time: {
    color: color.fgSecondary,
    fontSize: 13,
    marginTop: space.s8,
  },
});
