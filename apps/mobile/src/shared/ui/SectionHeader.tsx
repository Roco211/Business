import { StyleSheet, Text, View } from "react-native";

import { color, space } from "./tokens";

type SectionHeaderProps = {
  title: string;
  subtitle?: string;
};

export function SectionHeader({ title, subtitle }: SectionHeaderProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>{title}</Text>
      {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: space.s8,
  },
  title: {
    color: color.fgPrimary,
    fontSize: 20,
    fontWeight: "600",
  },
  subtitle: {
    color: color.fgSecondary,
    fontSize: 14,
  },
});

