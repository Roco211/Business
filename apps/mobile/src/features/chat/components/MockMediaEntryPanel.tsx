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
      <SectionHeader title="调试专用：历史样例提交" subtitle="仅供开发验证，不属于店员默认路径。" />
      {error ? <InlineNotice tone="error" title="调试动作失败" message={error} /> : null}
      <PrimaryButton
        label={voiceDemo.isSubmitting ? "调试提交中（语音）..." : "调试: 语音查询 (旧演示)"}
        onPress={() => {
          void handleVoiceSubmit("query");
        }}
        disabled={isSubmitting}
      />
      <PrimaryButton
        label={voiceDemo.isSubmitting ? "调试提交中（语音）..." : "调试: 语音入库 (旧演示)"}
        onPress={() => {
          void handleVoiceSubmit("stock_in");
        }}
        disabled={isSubmitting}
      />
      <PrimaryButton
        label={voiceDemo.isSubmitting ? "调试提交中（语音）..." : "调试: 语音出库 (旧演示)"}
        onPress={() => {
          void handleVoiceSubmit("stock_out");
        }}
        disabled={isSubmitting}
      />
      <PrimaryButton
        label={imageDemo.isSubmitting ? "调试提交中（图片）..." : "调试: 拍照查询 (旧演示)"}
        onPress={() => {
          void handleImageSubmit("query");
        }}
        disabled={isSubmitting}
      />
      <PrimaryButton
        label={imageDemo.isSubmitting ? "调试提交中（图片）..." : "调试: 拍照入库 (旧演示)"}
        onPress={() => {
          void handleImageSubmit("stock_in");
        }}
        disabled={isSubmitting}
      />
      <PrimaryButton
        label={receiptDemo.isSubmitting ? "调试提交中（票据）..." : "调试: 票据识别 (旧演示)"}
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
