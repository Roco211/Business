import { StyleSheet, Text, View } from "react-native";

import { color, space } from "./tokens";

type EmptyStateProps = {
  title: string;
  description: string;
};

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>{title}</Text>
      <Text style={styles.description}>{description}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
    gap: space.s8,
    paddingVertical: space.s24,
  },
  title: {
    color: color.fgPrimary,
    fontSize: 20,
    fontWeight: "600",
    textAlign: "center",
  },
  description: {
    color: color.fgSecondary,
    fontSize: 15,
    textAlign: "center",
  },
});

