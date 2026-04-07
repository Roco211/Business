import { StyleSheet, Text, TextInput, View, type TextInputProps } from "react-native";

import { color, radius, space } from "./tokens";

type AppTextFieldProps = Omit<TextInputProps, "onChangeText" | "value"> & {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
  error?: string;
};

export function AppTextField({ label, value, onChangeText, error, ...textInputProps }: AppTextFieldProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        value={value}
        onChangeText={onChangeText}
        style={[styles.input, error ? styles.inputError : null]}
        {...textInputProps}
      />
      {error ? <Text style={styles.error}>{error}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: space.s8,
  },
  label: {
    color: color.fgSecondary,
    fontSize: 14,
    fontWeight: "500",
  },
  input: {
    backgroundColor: color.bgSurface,
    borderColor: color.borderSubtle,
    borderRadius: radius.input,
    borderWidth: 1,
    color: color.fgPrimary,
    minHeight: 46,
    paddingHorizontal: space.s12,
    paddingVertical: space.s12,
  },
  inputError: {
    borderColor: color.statusError,
  },
  error: {
    color: color.statusError,
    fontSize: 13,
  },
});

