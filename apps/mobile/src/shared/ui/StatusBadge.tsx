import { StyleSheet, Text, View } from "react-native";

import { color, radius, space } from "./tokens";

type StatusTone = "warning" | "error" | "success" | "neutral";

type StatusBadgeProps = {
  tone: StatusTone;
  label: string;
};

const badgeColorByTone = {
  warning: color.statusWarning,
  error: color.statusError,
  success: color.statusSuccess,
  neutral: color.fgSecondary,
} as const;

export function StatusBadge({ tone, label }: StatusBadgeProps) {
  return (
    <View style={[styles.badge, { backgroundColor: badgeColorByTone[tone] }]}>
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: "flex-start",
    borderRadius: radius.pill,
    paddingHorizontal: space.s12,
    paddingVertical: 6,
  },
  label: {
    color: "#ffffff",
    fontSize: 12,
    fontWeight: "600",
  },
});

