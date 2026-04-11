import { StyleSheet, Text, View } from "react-native";

import { PillActionButton, StatusBadge, SurfaceCard, color, space } from "../../../shared/ui";
import { getWorkbenchConnectionCopy } from "../../../shared/session/getWorkbenchConnectionCopy";
import { useSessionStream } from "../../../shared/session/useSessionStream";
import { SessionStreamConnectionState } from "../../../shared/session/sessionStreamClient";

type WorkbenchHeaderProps = {
  title: string;
  sessionTitle: string;
  connectionState: SessionStreamConnectionState;
  bootstrapError?: string | null;
  hint?: string | null;
  onAction?: (() => void) | null;
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
  onAction = null,
}: WorkbenchHeaderProps) {
  const sessionStream = useSessionStream();
  const resolvedBootstrapError = bootstrapError ?? sessionStream.bootstrapError;
  const connectionCopy = getWorkbenchConnectionCopy({
    bootstrapError: resolvedBootstrapError,
    connectionState,
  });
  const resolvedHint = resolvedBootstrapError ? connectionCopy.hint : (hint ?? connectionCopy.hint);

  return (
    <SurfaceCard tone="muted" emphasis="elevated" style={styles.shell}>
      <View style={styles.container} testID="chat-workbench-header">
        <View style={styles.identityRow}>
          <View style={styles.brandBlock}>
            <View style={styles.brandMark}>
              <Text style={styles.brandMarkText}>S</Text>
            </View>
            <View style={styles.copyBlock}>
              <Text style={styles.title}>{title}</Text>
              <Text style={styles.sessionTitle}>{sessionTitle}</Text>
            </View>
          </View>
          <StatusBadge tone={getConnectionTone(connectionState)} label={connectionCopy.title} />
        </View>
        <Text style={styles.connectionLabel}>连接状态</Text>
        {resolvedHint ? <Text style={styles.hint}>{resolvedHint}</Text> : null}
        {connectionCopy.actionLabel && onAction ? (
          <PillActionButton label={connectionCopy.actionLabel} onPress={onAction} />
        ) : null}
      </View>
    </SurfaceCard>
  );
}

const styles = StyleSheet.create({
  shell: {
    gap: space.s12,
  },
  container: {
    gap: space.s12,
  },
  identityRow: {
    alignItems: "center",
    flexDirection: "row",
    gap: space.s12,
    justifyContent: "space-between",
  },
  brandBlock: {
    alignItems: "center",
    flex: 1,
    flexDirection: "row",
    gap: space.s12,
  },
  brandMark: {
    alignItems: "center",
    backgroundColor: color.bgBrandSoft,
    borderRadius: 18,
    height: 40,
    justifyContent: "center",
    width: 40,
  },
  brandMarkText: {
    color: color.accentPrimary,
    fontSize: 18,
    fontWeight: "700",
  },
  copyBlock: {
    flex: 1,
    gap: 2,
  },
  title: {
    color: color.fgPrimary,
    fontSize: 22,
    fontWeight: "700",
    letterSpacing: -0.4,
  },
  sessionTitle: {
    color: color.fgSecondary,
    fontSize: 13,
  },
  connectionLabel: {
    color: color.fgSecondary,
    fontSize: 13,
    fontWeight: "500",
  },
  hint: {
    color: color.fgSecondary,
    fontSize: 13,
    lineHeight: 19,
  },
});
