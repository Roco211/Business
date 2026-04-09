import { Pressable, StyleSheet, Text, View } from "react-native";

import { InlineNotice, SectionHeader, SurfaceCard, color, radius, space } from "../../../shared/ui";
import { useSendImageDemoMutation } from "../hooks/useSendImageDemoMutation";
import { useSendReceiptDemoMutation } from "../hooks/useSendReceiptDemoMutation";
import { useSendVoiceDemoMutation } from "../hooks/useSendVoiceDemoMutation";

const COPY = {
  title: "常用入口",
  subtitle: "语音、拍照和票据都可以从这里发起。",
  errorTitle: "提交未完成",
  voice: "语音查货",
  photo: "拍照入库",
  receipt: "票据识别",
} as const;

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
    <SurfaceCard tone="muted" style={styles.shell}>
      <View style={styles.container}>
        <SectionHeader title={COPY.title} subtitle={COPY.subtitle} />
        {error ? <InlineNotice tone="error" title={COPY.errorTitle} message={error} /> : null}
        <View style={styles.tileRow}>
          <Pressable
            testID="guided-pill-voice"
            accessibilityRole="button"
            onPress={() => {
              void handleVoiceEntry();
            }}
            disabled={isSubmitting}
            style={styles.tile}
          >
            <Text style={styles.tileTitle}>{COPY.voice}</Text>
            <Text style={styles.tileDetail}>一句话查看库存和缺货风险</Text>
          </Pressable>
          <Pressable
            testID="guided-pill-photo"
            accessibilityRole="button"
            onPress={() => {
              void handlePhotoEntry();
            }}
            disabled={isSubmitting}
            style={styles.tile}
          >
            <Text style={styles.tileTitle}>{COPY.photo}</Text>
            <Text style={styles.tileDetail}>对着商品拍照后继续确认</Text>
          </Pressable>
          <Pressable
            testID="guided-pill-receipt"
            accessibilityRole="button"
            onPress={() => {
              void handleReceiptEntry();
            }}
            disabled={isSubmitting}
            style={styles.tile}
          >
            <Text style={styles.tileTitle}>{COPY.receipt}</Text>
            <Text style={styles.tileDetail}>快速整理票据条目和金额</Text>
          </Pressable>
        </View>
      </View>
    </SurfaceCard>
  );
}

const styles = StyleSheet.create({
  shell: {
    gap: space.s12,
    paddingHorizontal: 0,
    paddingVertical: 0,
  },
  container: {
    gap: space.s12,
  },
  tileRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: space.s8,
  },
  tile: {
    backgroundColor: "rgba(255, 255, 255, 0.82)",
    borderColor: "rgba(45, 33, 28, 0.06)",
    borderRadius: radius.card,
    borderWidth: 1,
    flexGrow: 1,
    gap: 4,
    minWidth: "31%",
    paddingHorizontal: space.s12,
    paddingVertical: space.s12,
  },
  tileTitle: {
    color: color.fgPrimary,
    fontSize: 15,
    fontWeight: "600",
  },
  tileDetail: {
    color: color.fgSecondary,
    fontSize: 12,
    lineHeight: 18,
  },
});
