import { StyleSheet, Text, View } from "react-native";

import { SectionHeader, StatusBadge, SurfaceCard, color, space } from "../../../shared/ui";

type WorkbenchHeaderProps = {
  title: string;
  sessionTitle: string;
  connectionState: string;
  hint?: string | null;
};

const CONNECTION_STATE_LABELS: Record<string, string> = {
  connected: "已连接",
  connecting: "连接中",
  bootstrapping: "启动中",
  disconnected: "已断开",
  error: "连接异常",
};

function getConnectionTone(connectionState: string): "warning" | "error" | "success" | "neutral" {
  if (connectionState === "connected") {
    return "success";
  }
  if (connectionState === "connecting" || connectionState === "bootstrapping") {
    return "warning";
  }
  if (connectionState === "error" || connectionState === "disconnected") {
    return "error";
  }
  return "neutral";
}

function getConnectionLabel(connectionState: string) {
  return CONNECTION_STATE_LABELS[connectionState] ?? connectionState;
}

export function WorkbenchHeader({
  title,
  sessionTitle,
  connectionState,
  hint = null,
}: WorkbenchHeaderProps) {
  return (
    <SurfaceCard emphasis="elevated">
      <View style={styles.container} testID="chat-workbench-header">
        <SectionHeader title={title} subtitle={sessionTitle} />
        <View style={styles.connectionRow}>
          <Text style={styles.connectionLabel}>连接状态</Text>
          <StatusBadge tone={getConnectionTone(connectionState)} label={getConnectionLabel(connectionState)} />
        </View>
        {hint ? <Text style={styles.hint}>{hint}</Text> : null}
      </View>
    </SurfaceCard>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: space.s12,
  },
  connectionRow: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  connectionLabel: {
    color: color.fgSecondary,
    fontSize: 13,
    fontWeight: "500",
  },
  hint: {
    color: color.fgSecondary,
    fontSize: 13,
  },
});
