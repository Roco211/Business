import { StyleSheet, View } from "react-native";

import { InlineNotice, PrimaryButton, SectionHeader, space } from "../../../shared/ui";
import { useSendImageDemoMutation } from "../hooks/useSendImageDemoMutation";
import { useSendReceiptDemoMutation } from "../hooks/useSendReceiptDemoMutation";
import { useSendVoiceDemoMutation } from "../hooks/useSendVoiceDemoMutation";

export function MockMediaEntryPanel({
  sessionId,
  onSubmitted,
}: {
  sessionId: string | null;
  onSubmitted: () => void;
}) {
  const voiceDemo = useSendVoiceDemoMutation(sessionId);
  const imageDemo = useSendImageDemoMutation(sessionId);
  const receiptDemo = useSendReceiptDemoMutation(sessionId);

  const isSubmitting = voiceDemo.isSubmitting || imageDemo.isSubmitting || receiptDemo.isSubmitting;
  const error = voiceDemo.error ?? imageDemo.error ?? receiptDemo.error;

  async function handleVoiceSubmit(kind: "query" | "stock_in" | "stock_out") {
    const result = await voiceDemo.submitVoiceDemo(kind);
    if (result === null) {
      return;
    }
    onSubmitted();
  }

  async function handleImageSubmit(kind: "query" | "stock_in") {
    const result = await imageDemo.submitImageDemo(kind);
    if (result === null) {
      return;
    }
    onSubmitted();
  }

  async function handleReceiptSubmit() {
    const result = await receiptDemo.submitReceiptDemo();
    if (result === null) {
      return;
    }
    onSubmitted();
  }

  return (
    <View style={styles.container}>
      <SectionHeader title="Media demos" subtitle="Legacy debug entry points for demo uploads." />
      {error ? <InlineNotice tone="error" title="Demo failed" message={error} /> : null}
      <PrimaryButton
        label={voiceDemo.isSubmitting ? "Sending voice..." : "Voice Query Demo"}
        onPress={() => {
          void handleVoiceSubmit("query");
        }}
        disabled={isSubmitting}
      />
      <PrimaryButton
        label={voiceDemo.isSubmitting ? "Sending voice..." : "Voice Stock-In Demo"}
        onPress={() => {
          void handleVoiceSubmit("stock_in");
        }}
        disabled={isSubmitting}
      />
      <PrimaryButton
        label={voiceDemo.isSubmitting ? "Sending voice..." : "Voice Stock-Out Demo"}
        onPress={() => {
          void handleVoiceSubmit("stock_out");
        }}
        disabled={isSubmitting}
      />
      <PrimaryButton
        label={imageDemo.isSubmitting ? "Sending photo..." : "Photo Query Demo"}
        onPress={() => {
          void handleImageSubmit("query");
        }}
        disabled={isSubmitting}
      />
      <PrimaryButton
        label={imageDemo.isSubmitting ? "Sending photo..." : "Photo Stock-In Demo"}
        onPress={() => {
          void handleImageSubmit("stock_in");
        }}
        disabled={isSubmitting}
      />
      <PrimaryButton
        label={receiptDemo.isSubmitting ? "Sending receipt..." : "Receipt OCR Demo"}
        onPress={() => {
          void handleReceiptSubmit();
        }}
        disabled={isSubmitting}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: space.s8,
  },
});
