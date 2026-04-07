import type { PropsWithChildren } from "react";
import { StyleSheet, Text, View } from "react-native";

import { color, space } from "./tokens";

type AppScreenProps = PropsWithChildren<{
  title?: string;
  subtitle?: string;
  centerContent?: boolean;
  contentWidth?: number;
}>;

export function AppScreen({
  title,
  subtitle,
  centerContent = false,
  contentWidth = 640,
  children,
}: AppScreenProps) {
  return (
    <View style={[styles.screen, centerContent ? styles.centered : null]}>
      <View style={[styles.content, { maxWidth: contentWidth }]}>
        {title ? <Text style={styles.title}>{title}</Text> : null}
        {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
        <View style={styles.body}>{children}</View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    backgroundColor: color.bgApp,
    flex: 1,
    padding: space.s20,
  },
  centered: {
    justifyContent: "center",
  },
  content: {
    alignSelf: "center",
    width: "100%",
  },
  title: {
    color: color.fgPrimary,
    fontSize: 30,
    fontWeight: "700",
  },
  subtitle: {
    color: color.fgSecondary,
    fontSize: 16,
    marginTop: space.s8,
  },
  body: {
    gap: space.s12,
    marginTop: space.s16,
  },
});

