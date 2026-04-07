import { StyleSheet, Text, View } from "react-native";

import { SectionHeader, StatusBadge, SurfaceCard, color, space } from "../../../shared/ui";
import { getWorkbenchConnectionCopy } from "../../../shared/session/getWorkbenchConnectionCopy";
import { useSessionStream } from "../../../shared/session/useSessionStream";
import { SessionStreamConnectionState } from "../../../shared/session/sessionStreamClient";

type WorkbenchHeaderProps = {
  title: string;
  sessionTitle: string;
  connectionState: SessionStreamConnectionState;
  bootstrapError?: string | null;
  hint?: string | null;
};

function getConnectionTone(
  connectionState: SessionStreamConnectionState,
): "warning" | "error" | "success" | "neutral" {
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
  bootstrapError = null,
  hint = null,
}: WorkbenchHeaderProps) {
  const sessionStream = useSessionStream();
  const resolvedBootstrapError = bootstrapError ?? sessionStream.bootstrapError;
  const connectionCopy = getWorkbenchConnectionCopy({
    bootstrapError: resolvedBootstrapError,
    connectionState,
  });
  const resolvedHint = resolvedBootstrapError ? connectionCopy.hint : (hint ?? connectionCopy.hint);

  return (
    <SurfaceCard emphasis="elevated">
      <View style={styles.container} testID="chat-workbench-header">
        <SectionHeader title={title} subtitle={sessionTitle} />
        <View style={styles.connectionRow}>
          <Text style={styles.connectionLabel}>连接状态</Text>
          <StatusBadge tone={getConnectionTone(connectionState)} label={connectionCopy.title} />
        </View>
        {resolvedHint ? <Text style={styles.hint}>{resolvedHint}</Text> : null}
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
