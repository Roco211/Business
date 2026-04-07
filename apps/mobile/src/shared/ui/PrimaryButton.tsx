import { Pressable, StyleSheet, Text, type PressableProps } from "react-native";

import { color, radius, space } from "./tokens";

type PrimaryButtonProps = Omit<PressableProps, "children"> & {
  label: string;
  loading?: boolean;
  loadingLabel?: string;
};

export function PrimaryButton({
  label,
  loading = false,
  loadingLabel = "Loading...",
  disabled,
  ...pressableProps
}: PrimaryButtonProps) {
  const isDisabled = Boolean(disabled || loading);
  const copy = loading ? loadingLabel : label;

  return (
    <Pressable
      accessibilityRole="button"
      style={[styles.button, isDisabled ? styles.buttonDisabled : null]}
      disabled={isDisabled}
      {...pressableProps}
    >
      <Text style={styles.label}>{copy}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    alignItems: "center",
    backgroundColor: color.accentPrimary,
    borderRadius: radius.input,
    justifyContent: "center",
    minHeight: 48,
    paddingHorizontal: space.s16,
    paddingVertical: space.s12,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  label: {
    color: "#ffffff",
    fontSize: 16,
    fontWeight: "600",
  },
});

