import type { PropsWithChildren } from "react";
import { StyleSheet, View, type StyleProp, type ViewStyle } from "react-native";

import { color, radius, space } from "./tokens";

type SurfaceTone = "default" | "muted" | "inverse";
type SurfaceEmphasis = "none" | "outlined" | "elevated";

type SurfaceCardProps = PropsWithChildren<{
  tone?: SurfaceTone;
  emphasis?: SurfaceEmphasis;
  style?: StyleProp<ViewStyle>;
}>;

export function SurfaceCard({
  tone = "default",
  emphasis = "none",
  style,
  children,
}: SurfaceCardProps) {
  const toneStyle = toneStyles[tone];
  const emphasisStyle = emphasisStyles[emphasis];

  return <View style={[styles.base, toneStyle, emphasisStyle, style]}>{children}</View>;
}

const styles = StyleSheet.create({
  base: {
    borderRadius: radius.panel,
    padding: space.s16,
  },
});

const toneStyles = StyleSheet.create({
  default: {
    backgroundColor: color.bgSurface,
  },
  muted: {
    backgroundColor: color.bgMuted,
  },
  inverse: {
    backgroundColor: color.bgInverse,
  },
});

const emphasisStyles = StyleSheet.create({
  none: {},
  outlined: {
    borderColor: color.borderSubtle,
    borderWidth: 1,
  },
  elevated: {
    borderColor: "rgba(255,255,255,0.65)",
    borderWidth: 1,
    elevation: 3,
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.08,
    shadowRadius: 18,
  },
});
