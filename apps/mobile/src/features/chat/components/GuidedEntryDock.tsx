import { StyleSheet, View } from "react-native";

import { InlineNotice, PillActionButton, SectionHeader, SurfaceCard, space } from "../../../shared/ui";
import { useSendImageDemoMutation } from "../hooks/useSendImageDemoMutation";
import { useSendReceiptDemoMutation } from "../hooks/useSendReceiptDemoMutation";
import { useSendVoiceDemoMutation } from "../hooks/useSendVoiceDemoMutation";

type GuidedEntryDockProps = {
  sessionId: string | null;
  onSubmitted: () => void;
};

export function GuidedEntryDock({ sessionId, onSubmitted }: GuidedEntryDockProps) {
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
        <SectionHeader title="引导入口" subtitle="先用语音、拍照或票据发起任务。" />
        {error ? <InlineNotice tone="error" title="Submission failed" message={error} /> : null}
        <View style={styles.pillRow}>
          <PillActionButton
            testID="guided-pill-voice"
            label="语音"
            onPress={() => {
              void handleVoiceEntry();
            }}
            disabled={isSubmitting}
          />
          <PillActionButton
            testID="guided-pill-photo"
            label="拍照"
            onPress={() => {
              void handlePhotoEntry();
            }}
            disabled={isSubmitting}
          />
          <PillActionButton
            testID="guided-pill-receipt"
            label="票据"
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
});
