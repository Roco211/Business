import type { PropsWithChildren } from "react";
import { StyleSheet, Text, View } from "react-native";

import {
  InlineNotice,
  PillActionButton,
  PrimaryButton,
  StatusBadge,
  SurfaceCard,
  color,
  space,
} from "../../../shared/ui";

type ConfirmationCardShellProps = PropsWithChildren<{
  confirmationId: string;
  title: string;
  summary?: string;
  transcript?: string;
  error?: string | null;
  approveLabel: string;
  rejectLabel: string;
  approveLoadingLabel: string;
  rejectLoadingLabel: string;
  isApproveSubmitting: boolean;
  isRejectSubmitting: boolean;
  isSubmitting: boolean;
  onApprove: () => void;
  onReject: () => void;
}>;

const COPY = {
  pendingReview: "待复核",
  actionFailed: "操作失败",
  intervention: "人工介入",
} as const;

export function ConfirmationCardShell({
  confirmationId,
  title,
  summary,
  transcript,
  error,
  approveLabel,
  rejectLabel,
  approveLoadingLabel,
  rejectLoadingLabel,
  isApproveSubmitting,
  isRejectSubmitting,
  isSubmitting,
  onApprove,
  onReject,
  children,
}: ConfirmationCardShellProps) {
  return (
    <SurfaceCard emphasis="elevated" style={styles.shell}>
      <View style={styles.container}>
        <Text style={styles.kicker}>{COPY.intervention}</Text>
        <View style={styles.headerRow}>
          <Text style={styles.title}>{title}</Text>
          <StatusBadge tone="warning" label={COPY.pendingReview} />
        </View>
        {summary ? <Text style={styles.summary}>{summary}</Text> : null}
        {transcript ? <Text style={styles.transcript}>{transcript}</Text> : null}
        <View style={styles.fields}>{children}</View>
        {error ? <InlineNotice tone="error" title={COPY.actionFailed} message={error} /> : null}
        <View style={styles.actions}>
          <PrimaryButton
            testID={`confirm-approve-${confirmationId}`}
            label={approveLabel}
            loading={isApproveSubmitting}
            loadingLabel={approveLoadingLabel}
            onPress={onApprove}
            disabled={isSubmitting}
          />
          <PillActionButton
            testID={`confirm-reject-${confirmationId}`}
            label={isRejectSubmitting ? rejectLoadingLabel : rejectLabel}
            onPress={onReject}
            disabled={isSubmitting}
          />
        </View>
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
  kicker: {
    color: color.accentPrimary,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.4,
  },
  headerRow: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  title: {
    color: color.fgPrimary,
    flexShrink: 1,
    fontSize: 18,
    fontWeight: "600",
    paddingRight: space.s8,
  },
  summary: {
    color: color.fgPrimary,
    fontSize: 14,
    lineHeight: 20,
  },
  transcript: {
    color: color.fgSecondary,
    fontSize: 13,
    lineHeight: 18,
  },
  fields: {
    backgroundColor: color.bgMuted,
    borderRadius: 20,
    gap: space.s8,
    padding: space.s12,
  },
  actions: {
    gap: space.s8,
  },
});
