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
  style,
  ...pressableProps
}: PrimaryButtonProps) {
  const isDisabled = Boolean(disabled || loading);
  const copy = loading ? loadingLabel : label;

  return (
    <Pressable
      accessibilityRole="button"
      style={(state) => [
        styles.button,
        isDisabled ? styles.buttonDisabled : null,
        typeof style === "function" ? style(state) : style,
      ]}
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
    minHeight: 52,
    paddingHorizontal: space.s16,
    paddingVertical: space.s12,
    shadowColor: "#1f4d35",
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.12,
    shadowRadius: 14,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  label: {
    color: color.accentContrast,
    fontSize: 16,
    fontWeight: "600",
  },
});
