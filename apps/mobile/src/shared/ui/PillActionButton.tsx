import { Pressable, StyleSheet, Text, type PressableProps } from "react-native";

import { color, radius, space } from "./tokens";

type PillActionButtonProps = Omit<PressableProps, "children"> & {
  label: string;
};

export function PillActionButton({ label, disabled, ...pressableProps }: PillActionButtonProps) {
  return (
    <Pressable
      accessibilityRole="button"
      style={[styles.button, disabled ? styles.disabled : null]}
      disabled={disabled}
      {...pressableProps}
    >
      <Text style={styles.label}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    alignItems: "center",
    backgroundColor: color.bgSurface,
    borderColor: color.borderSubtle,
    borderRadius: radius.pill,
    borderWidth: 1,
    justifyContent: "center",
    minHeight: 40,
    paddingHorizontal: space.s16,
    paddingVertical: space.s8,
  },
  disabled: {
    opacity: 0.5,
  },
  label: {
    color: color.fgPrimary,
    fontSize: 15,
    fontWeight: "500",
  },
});

