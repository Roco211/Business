import { StyleSheet, View } from "react-native";

import { InlineNotice, PillActionButton, SectionHeader, SurfaceCard, color, space } from "../../../shared/ui";
import { useSendImageDemoMutation } from "../hooks/useSendImageDemoMutation";
import { useSendReceiptDemoMutation } from "../hooks/useSendReceiptDemoMutation";
import { useSendVoiceDemoMutation } from "../hooks/useSendVoiceDemoMutation";
import type { WorkbenchIntent } from "../workbenchIntent";

const COPY = {
  title: "业务快捷入口",
  subtitle: "用语音盘点、拍照识别或票据录入发起任务。",
  errorTitle: "提交未完成",
  voice: "语音盘点",
  photo: "拍照识别",
  receipt: "票据录入",
} as const;

type GuidedEntryDockProps = {
  sessionId: string | null;
  onSubmitted: () => void;
  highlightedIntent?: WorkbenchIntent | null;
};

export function GuidedEntryDock({
  sessionId,
  onSubmitted,
  highlightedIntent = null,
}: GuidedEntryDockProps) {
  const voiceDemo = useSendVoiceDemoMutation(sessionId);
  const imageDemo = useSendImageDemoMutation(sessionId);
  const receiptDemo = useSendReceiptDemoMutation(sessionId);

  const isSubmitting = voiceDemo.isSubmitting || imageDemo.isSubmitting || receiptDemo.isSubmitting;
  const error = voiceDemo.error ?? imageDemo.error ?? receiptDemo.error;

  async function handleVoiceEntry() {
    const result = await voiceDemo.submitVoiceDemo("query");
    if (result === null) {
      return;
    }
    onSubmitted();
  }

  async function handlePhotoEntry() {
    const result = await imageDemo.submitImageDemo("query");
    if (result === null) {
      return;
    }
    onSubmitted();
  }

  async function handleReceiptEntry() {
    const result = await receiptDemo.submitReceiptDemo();
    if (result === null) {
      return;
    }
    onSubmitted();
  }

  return (
    <SurfaceCard tone="muted" emphasis="outlined">
      <View style={styles.container}>
        <SectionHeader title={COPY.title} subtitle={COPY.subtitle} />
        {error ? <InlineNotice tone="error" title={COPY.errorTitle} message={error} /> : null}
        <View style={styles.pillRow}>
          <PillActionButton
            testID="guided-pill-voice"
            label={COPY.voice}
            accessibilityState={{ selected: highlightedIntent === "voice-query" }}
            style={highlightedIntent === "voice-query" ? styles.pillSelected : undefined}
            onPress={() => {
              void handleVoiceEntry();
            }}
            disabled={isSubmitting}
          />
          <PillActionButton
            testID="guided-pill-photo"
            label={COPY.photo}
            accessibilityState={{ selected: highlightedIntent === "photo-stock-in" }}
            style={highlightedIntent === "photo-stock-in" ? styles.pillSelected : undefined}
            onPress={() => {
              void handlePhotoEntry();
            }}
            disabled={isSubmitting}
          />
          <PillActionButton
            testID="guided-pill-receipt"
            label={COPY.receipt}
            accessibilityState={{ selected: highlightedIntent === "receipt-entry" }}
            style={highlightedIntent === "receipt-entry" ? styles.pillSelected : undefined}
            onPress={() => {
              void handleReceiptEntry();
            }}
            disabled={isSubmitting}
          />
        </View>
      </View>
    </SurfaceCard>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: space.s12,
  },
  pillRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: space.s8,
  },
  pillSelected: {
    backgroundColor: color.focusRing,
    borderColor: color.accentPrimary,
  },
});
