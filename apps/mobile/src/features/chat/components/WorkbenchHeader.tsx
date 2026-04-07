import { StyleSheet, Text, View } from "react-native";

import { SectionHeader, StatusBadge, SurfaceCard, color, space } from "../../../shared/ui";

type WorkbenchHeaderProps = {
  title: string;
  sessionTitle: string;
  connectionState: string;
  hint?: string | null;
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
          <Text style={styles.connectionLabel}>Connection</Text>
          <StatusBadge tone={getConnectionTone(connectionState)} label={connectionState} />
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
