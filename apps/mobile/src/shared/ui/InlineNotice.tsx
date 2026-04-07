import { StyleSheet, Text, View } from "react-native";

import { color, radius, space } from "./tokens";

type NoticeTone = "neutral" | "warning" | "error" | "success";

type InlineNoticeProps = {
  tone: NoticeTone;
  message: string;
  title?: string;
};

const backgroundByTone = {
  neutral: "rgba(29, 29, 31, 0.05)",
  warning: "rgba(178, 107, 0, 0.12)",
  error: "rgba(198, 40, 40, 0.12)",
  success: "rgba(31, 143, 76, 0.12)",
} as const;

const foregroundByTone = {
  neutral: color.fgPrimary,
  warning: color.statusWarning,
  error: color.statusError,
  success: color.statusSuccess,
} as const;

export function InlineNotice({ tone, message, title }: InlineNoticeProps) {
  return (
    <View style={[styles.container, { backgroundColor: backgroundByTone[tone] }]}>
      {title ? <Text style={[styles.title, { color: foregroundByTone[tone] }]}>{title}</Text> : null}
      <Text style={[styles.message, { color: foregroundByTone[tone] }]}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderRadius: radius.card,
    gap: space.s8,
    padding: space.s12,
  },
  title: {
    fontSize: 14,
    fontWeight: "600",
  },
  message: {
    fontSize: 14,
  },
});

