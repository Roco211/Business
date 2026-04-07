import { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from "react-native";

import { getFriendlyStatusMessage } from "../../../shared/copy/getFriendlyStatusMessage";
import { AppScreen, AppTextField, InlineNotice, PrimaryButton, SurfaceCard, color, space } from "../../../shared/ui";
import { useLoginMutation } from "../hooks/useLoginMutation";

export default function LoginScreen() {
  const [email, setEmail] = useState("owner@example.com");
  const [password, setPassword] = useState("dev-password");
  const login = useLoginMutation();

  return (
    <AppScreen centerContent contentWidth={420}>
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={Platform.OS === "ios" ? 24 : 0}
        style={styles.keyboardAvoid}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.hero}>
            <Text style={styles.kicker}>门店试点</Text>
            <Text style={styles.title}>{"\u95e8\u5e97\u5e93\u5b58\u52a9\u624b"}</Text>
            <Text style={styles.subtitle}>{"\u8bed\u97f3\u3001\u62cd\u7167\u3001\u7968\u636e\u7edf\u4e00\u5165\u8d26"}</Text>
          </View>
          <SurfaceCard emphasis="outlined" style={styles.card}>
            <AppTextField
              label={"\u90ae\u7bb1"}
              autoCapitalize="none"
              keyboardType="email-address"
              onChangeText={setEmail}
              placeholder="owner@example.com"
              value={email}
            />
            <AppTextField
              label={"\u5bc6\u7801"}
              onChangeText={setPassword}
              placeholder={"\u8bf7\u8f93\u5165\u5bc6\u7801"}
              secureTextEntry
              value={password}
            />
            {login.error ? (
              <InlineNotice
                tone="error"
                title="暂时无法登录"
                message={getFriendlyStatusMessage(login.error, "登录暂时不可用，请稍后再试。")}
              />
            ) : null}
            <PrimaryButton
              label={"\u767b\u5f55"}
              loading={login.isSubmitting}
              loadingLabel="正在登录..."
              onPress={() => void login.submitLogin(email, password)}
            />
          </SurfaceCard>
        </ScrollView>
      </KeyboardAvoidingView>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  keyboardAvoid: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    justifyContent: "center",
    paddingBottom: space.s20,
  },
  hero: {
    gap: space.s8,
    marginBottom: space.s12,
  },
  kicker: {
    color: color.fgTertiary,
    fontSize: 12,
    fontWeight: "600",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  title: {
    color: color.fgPrimary,
    fontSize: 32,
    fontWeight: "700",
  },
  subtitle: {
    color: color.fgSecondary,
    fontSize: 16,
  },
  card: {
    gap: space.s12,
  },
});
