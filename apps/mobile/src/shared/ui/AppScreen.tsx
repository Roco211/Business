import type { PropsWithChildren } from "react";
import { StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { color, space } from "./tokens";

type AppScreenProps = PropsWithChildren<{
  title?: string;
  subtitle?: string;
  centerContent?: boolean;
  contentWidth?: number;
  safeArea?: boolean;
}>;

export function AppScreen({
  title,
  subtitle,
  centerContent = false,
  contentWidth = 640,
  safeArea = true,
  children,
}: AppScreenProps) {
  const Container = safeArea ? SafeAreaView : View;

  return (
    <Container style={[styles.screen, centerContent ? styles.centered : null]}>
      <View style={[styles.content, { maxWidth: contentWidth }]}>
        {title ? <Text style={styles.title}>{title}</Text> : null}
        {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
        <View style={styles.body}>{children}</View>
      </View>
    </Container>
  );
}

const styles = StyleSheet.create({
  screen: {
    backgroundColor: color.bgApp,
    flex: 1,
    paddingHorizontal: space.s20,
    paddingTop: space.s24,
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
    fontSize: 32,
    fontWeight: "700",
    letterSpacing: -0.6,
  },
  subtitle: {
    color: color.fgSecondary,
    fontSize: 15,
    lineHeight: 22,
    marginTop: space.s8,
  },
  body: {
    gap: space.s12,
    marginTop: space.s20,
  },
});
