import { useEffect, useState } from "react";
import { StyleSheet, View } from "react-native";

import { InlineNotice, PillActionButton, SectionHeader, SurfaceCard, color, space } from "../../../shared/ui";
import { useSendImageDemoMutation } from "../hooks/useSendImageDemoMutation";
import { useSendReceiptDemoMutation } from "../hooks/useSendReceiptDemoMutation";
import { useSendVoiceDemoMutation } from "../hooks/useSendVoiceDemoMutation";
import type { WorkbenchIntent } from "../workbenchIntent";

const COPY = {
  title: "业务快捷入口",
  subtitle: "用语音盘点、拍照入库或票据录入发起任务。",
  rehearsalTitle: "流程演练说明",
  rehearsalMessage: "当前为流程演练，会提交预设样例请求。",
  sessionUnavailableTitle: "会话暂不可用",
  sessionUnavailableMessage: "会话尚未就绪，暂时不能提交演练请求。",
  errorTitle: "提交失败",
  genericErrorMessage: "请求未成功，请稍后重试。",
  successTitle: "已提交",
  successMessage: "正在处理中，如需复核请查看下方的待确认区域。",
  voiceSubmitting: "正在提交语音查货请求",
  photoSubmitting: "正在提交拍照入库请求",
  receiptSubmitting: "正在提交票据识别请求",
  voice: "语音盘点",
  photo: "拍照入库",
  receipt: "票据录入",
} as const;

type GuidedEntryStatus =
  | { tone: "neutral" | "success" | "error"; title: string; message: string }
  | null;
type GuidedEntryType = "voice" | "photo" | "receipt" | null;

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
  const [status, setStatus] = useState<GuidedEntryStatus>(null);
  const [activeEntry, setActiveEntry] = useState<GuidedEntryType>(null);

  const voiceDemo = useSendVoiceDemoMutation(sessionId);
  const imageDemo = useSendImageDemoMutation(sessionId);
  const receiptDemo = useSendReceiptDemoMutation(sessionId);

  const isSessionAvailable = sessionId !== null;
  const isSubmitting = voiceDemo.isSubmitting || imageDemo.isSubmitting || receiptDemo.isSubmitting;
  const isDockDisabled = isSubmitting || !isSessionAvailable;
  const activeEntryError =
    activeEntry === "voice"
      ? voiceDemo.error
      : activeEntry === "photo"
        ? imageDemo.error
        : activeEntry === "receipt"
          ? receiptDemo.error
          : null;

  useEffect(() => {
    if (!isSessionAvailable || !activeEntryError) {
      return;
    }
    setStatus({
      tone: "error",
      title: COPY.errorTitle,
      message: activeEntryError,
    });
  }, [activeEntryError, isSessionAvailable]);

  async function handleVoiceEntry() {
    if (!isSessionAvailable) {
      return;
    }
    setActiveEntry("voice");
    setStatus({
      tone: "neutral",
      title: COPY.voiceSubmitting,
      message: "",
    });
    const result = await voiceDemo.submitVoiceDemo("query");
    if (result === null) {
      setStatus((currentStatus) =>
        currentStatus?.tone === "error"
          ? currentStatus
          : {
              tone: "error",
              title: COPY.errorTitle,
              message: COPY.genericErrorMessage,
            },
      );
      return;
    }
    setStatus({
      tone: "success",
      title: COPY.successTitle,
      message: COPY.successMessage,
    });
    onSubmitted();
  }

  async function handlePhotoEntry() {
    if (!isSessionAvailable) {
      return;
    }
    setActiveEntry("photo");
    setStatus({
      tone: "neutral",
      title: COPY.photoSubmitting,
      message: "",
    });
    const result = await imageDemo.submitImageDemo("stock_in");
    if (result === null) {
      setStatus((currentStatus) =>
        currentStatus?.tone === "error"
          ? currentStatus
          : {
              tone: "error",
              title: COPY.errorTitle,
              message: COPY.genericErrorMessage,
            },
      );
      return;
    }
    setStatus({
      tone: "success",
      title: COPY.successTitle,
      message: COPY.successMessage,
    });
    onSubmitted();
  }

  async function handleReceiptEntry() {
    if (!isSessionAvailable) {
      return;
    }
    setActiveEntry("receipt");
    setStatus({
      tone: "neutral",
      title: COPY.receiptSubmitting,
      message: "",
    });
    const result = await receiptDemo.submitReceiptDemo();
    if (result === null) {
      setStatus((currentStatus) =>
        currentStatus?.tone === "error"
          ? currentStatus
          : {
              tone: "error",
              title: COPY.errorTitle,
              message: COPY.genericErrorMessage,
            },
      );
      return;
    }
    setStatus({
      tone: "success",
      title: COPY.successTitle,
      message: COPY.successMessage,
    });
    onSubmitted();
  }

  return (
    <SurfaceCard tone="muted" emphasis="outlined">
      <View style={styles.container}>
        <SectionHeader title={COPY.title} subtitle={COPY.subtitle} />
        <InlineNotice tone="neutral" title={COPY.rehearsalTitle} message={COPY.rehearsalMessage} />
        {!isSessionAvailable ? (
          <InlineNotice
            tone="neutral"
            title={COPY.sessionUnavailableTitle}
            message={COPY.sessionUnavailableMessage}
          />
        ) : null}
        {status ? <InlineNotice tone={status.tone} title={status.title} message={status.message} /> : null}
        <View style={styles.pillRow}>
          <PillActionButton
            testID="guided-pill-voice"
            label={COPY.voice}
            accessibilityState={{ selected: highlightedIntent === "voice-query" }}
            style={highlightedIntent === "voice-query" ? styles.pillSelected : undefined}
            onPress={() => {
              void handleVoiceEntry();
            }}
            disabled={isDockDisabled}
          />
          <PillActionButton
            testID="guided-pill-photo"
            label={COPY.photo}
            accessibilityState={{ selected: highlightedIntent === "photo-stock-in" }}
            style={highlightedIntent === "photo-stock-in" ? styles.pillSelected : undefined}
            onPress={() => {
              void handlePhotoEntry();
            }}
            disabled={isDockDisabled}
          />
          <PillActionButton
            testID="guided-pill-receipt"
            label={COPY.receipt}
            accessibilityState={{ selected: highlightedIntent === "receipt-entry" }}
            style={highlightedIntent === "receipt-entry" ? styles.pillSelected : undefined}
            onPress={() => {
              void handleReceiptEntry();
            }}
            disabled={isDockDisabled}
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
