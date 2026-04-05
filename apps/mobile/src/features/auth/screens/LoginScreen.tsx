import { useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { useLoginMutation } from "../hooks/useLoginMutation";

export default function LoginScreen() {
  const [email, setEmail] = useState("owner@example.com");
  const [password, setPassword] = useState("dev-password");
  const login = useLoginMutation();

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Sign In</Text>
      <TextInput
        accessibilityLabel="Email"
        autoCapitalize="none"
        keyboardType="email-address"
        onChangeText={setEmail}
        placeholder="owner@example.com"
        style={styles.input}
        value={email}
      />
      <TextInput
        accessibilityLabel="Password"
        onChangeText={setPassword}
        placeholder="password"
        secureTextEntry
        style={styles.input}
        value={password}
      />
      <Pressable style={styles.button} onPress={() => void login.submitLogin(email, password)}>
        <Text style={styles.buttonLabel}>{login.isSubmitting ? "Signing in..." : "Sign In"}</Text>
      </Pressable>
      {login.isSubmitting ? <ActivityIndicator /> : null}
      {login.error ? <Text style={styles.error}>{login.error}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: "stretch",
    flex: 1,
    gap: 12,
    justifyContent: "center",
    padding: 24,
  },
  title: {
    fontSize: 24,
    fontWeight: "600",
    textAlign: "center",
  },
  input: {
    borderColor: "#d1d5db",
    borderRadius: 8,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  button: {
    alignItems: "center",
    backgroundColor: "#111827",
    borderRadius: 8,
    paddingVertical: 12,
  },
  buttonLabel: {
    color: "#ffffff",
    fontWeight: "600",
  },
  error: {
    color: "#b91c1c",
    textAlign: "center",
  },
});
