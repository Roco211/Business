import type { PropsWithChildren } from "react";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { color, radius, space } from "./tokens";

type DebugDisclosureProps = PropsWithChildren<{
  defaultOpen?: boolean;
  title: string;
}>;

const COPY = {
  show: "展开调试信息",
  hide: "收起调试信息",
} as const;

export function DebugDisclosure({ title, children, defaultOpen = false }: DebugDisclosureProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <View style={styles.container}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={title}
        accessibilityState={{ expanded: isOpen }}
        onPress={() => setIsOpen((previous) => !previous)}
        style={styles.trigger}
      >
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.chevron}>{isOpen ? COPY.hide : COPY.show}</Text>
      </Pressable>
      {isOpen ? <View style={styles.body}>{children}</View> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderColor: color.borderSubtle,
    borderRadius: radius.card,
    borderWidth: 1,
    overflow: "hidden",
  },
  trigger: {
    alignItems: "center",
    backgroundColor: color.bgApp,
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: space.s12,
    paddingVertical: space.s12,
  },
  title: {
    color: color.fgSecondary,
    fontSize: 14,
    fontWeight: "500",
  },
  chevron: {
    color: color.fgTertiary,
    fontSize: 13,
  },
  body: {
    backgroundColor: color.bgApp,
    borderTopColor: color.borderSubtle,
    borderTopWidth: 1,
    padding: space.s12,
  },
});
