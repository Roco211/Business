import { StyleSheet, Text, View } from "react-native";

import { StatusBadge, SurfaceCard, color, space } from "../../../shared/ui";

type MessageResultCardProps = {
  messageId: string;
  actorLabel: string;
  actorType: string;
  messageType: string;
  text: string;
  createdAt: string;
};

const MESSAGE_TYPE_LABELS: Record<string, string> = {
  text: "文本",
  voice: "语音",
  image: "图片",
  "receipt-image": "票据",
};

const FALLBACK_MESSAGE_TYPE_LABEL = "其他";

function getActorTone(actorType: string): "warning" | "error" | "success" | "neutral" {
  if (actorType === "owner") {
    return "success";
  }
  if (actorType === "system") {
    return "neutral";
  }
  return "warning";
}

function getMessageTypeLabel(messageType: string) {
  return MESSAGE_TYPE_LABELS[messageType] ?? FALLBACK_MESSAGE_TYPE_LABEL;
}

export function MessageResultCard({
  messageId,
  actorLabel,
  actorType,
  messageType,
  text,
  createdAt,
}: MessageResultCardProps) {
  return (
    <View testID={`message-card-${messageId}`}>
      <SurfaceCard tone="default" emphasis="outlined">
        <View style={styles.container}>
          <View style={styles.headerRow}>
            <StatusBadge tone={getActorTone(actorType)} label={actorLabel} />
            <Text style={styles.timestamp}>{createdAt}</Text>
          </View>
          <Text style={styles.messageText}>{text}</Text>
          <Text style={styles.messageType}>类型：{getMessageTypeLabel(messageType)}</Text>
        </View>
      </SurfaceCard>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: space.s8,
  },
  headerRow: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
  },
  timestamp: {
    color: color.fgTertiary,
    fontSize: 12,
  },
  messageText: {
    color: color.fgPrimary,
    fontSize: 15,
    lineHeight: 21,
  },
  messageType: {
    color: color.fgSecondary,
    fontSize: 12,
  },
});
