import { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, View } from "react-native";

import { getApiBaseUrl } from "../../../shared/api/client";
import { getFriendlyStatusMessage } from "../../../shared/copy/getFriendlyStatusMessage";
import {
  AppScreen,
  AppTextField,
  DebugDisclosure,
  InlineNotice,
  PrimaryButton,
  SurfaceCard,
  color,
  space,
} from "../../../shared/ui";
import { useLoginMutation } from "../hooks/useLoginMutation";

const LOGIN_SCREEN_COPY = {
  kicker: "\u95e8\u5e97\u8bd5\u8fd0\u884c",
  title: "\u5148\u786e\u8ba4\u8fde\u63a5\uff0c\u518d\u5f00\u59cb\u4eca\u65e5\u5165\u5e93",
  subtitle: "\u767b\u5f55\u540e\u5373\u53ef\u7ee7\u7eed\u8bed\u97f3\u3001\u62cd\u7167\u548c\u7968\u636e\u5165\u8d26",
  helper: "\u73af\u5883\u5730\u5740\u4ec5\u4f9b\u6392\u67e5\uff0c\u65e5\u5e38\u53ef\u76f4\u63a5\u767b\u5f55\u3002",
  emailLabel: "\u90ae\u7bb1",
  passwordLabel: "\u5bc6\u7801",
  passwordPlaceholder: "\u8bf7\u8f93\u5165\u5bc6\u7801",
  loginLabel: "\u767b\u5f55",
  loadingLabel: "\u6b63\u5728\u767b\u5f55...",
  loginErrorTitle: "\u6682\u65f6\u65e0\u6cd5\u767b\u5f55",
  loginErrorFallback: "\u767b\u5f55\u6682\u65f6\u4e0d\u53ef\u7528\uff0c\u8bf7\u7a0d\u540e\u518d\u8bd5\u3002",
  troubleshootingTitle: "\u8fde\u63a5\u6392\u67e5",
  currentServiceLabel: "\u5f53\u524d\u95e8\u5e97\u670d\u52a1",
  stepCheckService: "\u68c0\u67e5\u672c\u673a\u6216\u95e8\u5e97\u670d\u52a1\u662f\u5426\u5df2\u542f\u52a8",
  stepAndroidEmulator:
    "\u82e5\u5728\u5b89\u5353\u6a21\u62df\u5668\u4e2d\u8fd0\u884c\uff0c\u8bf7\u786e\u8ba4\u540e\u7aef\u4f7f\u7528 10.0.2.2",
  stepDeviceNetwork:
    "\u82e5\u662f\u771f\u673a\u6d4b\u8bd5\uff0c\u8bf7\u786e\u4fdd\u8bbe\u5907\u4e0e\u5f00\u53d1\u673a\u5728\u540c\u4e00\u7f51\u7edc",
} as const;

export default function LoginScreen() {
  const [email, setEmail] = useState("owner@example.com");
  const [password, setPassword] = useState("dev-password");
  const login = useLoginMutation();
  const apiBaseUrl = getApiBaseUrl();
  const hasLoginError = Boolean(login.error);
  const troubleshootingSteps = [
    LOGIN_SCREEN_COPY.stepCheckService,
    LOGIN_SCREEN_COPY.stepAndroidEmulator,
    LOGIN_SCREEN_COPY.stepDeviceNetwork,
  ];

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
            <Text style={styles.kicker}>{LOGIN_SCREEN_COPY.kicker}</Text>
            <Text style={styles.title}>{LOGIN_SCREEN_COPY.title}</Text>
            <Text style={styles.subtitle}>{LOGIN_SCREEN_COPY.subtitle}</Text>
            <Text style={styles.helper}>{LOGIN_SCREEN_COPY.helper}</Text>
          </View>
          <SurfaceCard emphasis="outlined" style={styles.card}>
            <AppTextField
              label={LOGIN_SCREEN_COPY.emailLabel}
              autoCapitalize="none"
              keyboardType="email-address"
              onChangeText={setEmail}
              placeholder="owner@example.com"
              value={email}
            />
            <AppTextField
              label={LOGIN_SCREEN_COPY.passwordLabel}
              onChangeText={setPassword}
              placeholder={LOGIN_SCREEN_COPY.passwordPlaceholder}
              secureTextEntry
              value={password}
            />
            {login.error ? (
              <InlineNotice
                tone="error"
                title={LOGIN_SCREEN_COPY.loginErrorTitle}
                message={getFriendlyStatusMessage(login.error, LOGIN_SCREEN_COPY.loginErrorFallback)}
              />
            ) : null}
            <DebugDisclosure
              defaultOpen={hasLoginError}
              key={hasLoginError ? "login-troubleshooting-open" : "login-troubleshooting-closed"}
              title={LOGIN_SCREEN_COPY.troubleshootingTitle}
            >
              <View style={styles.troubleshootingBody}>
                <Text style={styles.troubleshootingLabel}>{LOGIN_SCREEN_COPY.currentServiceLabel}</Text>
                <Text style={styles.troubleshootingValue}>{apiBaseUrl}</Text>
                {troubleshootingSteps.map((step) => (
                  <Text key={step} style={styles.troubleshootingStep}>
                    {`\u2022 ${step}`}
                  </Text>
                ))}
              </View>
            </DebugDisclosure>
            <PrimaryButton
              label={LOGIN_SCREEN_COPY.loginLabel}
              loading={login.isSubmitting}
              loadingLabel={LOGIN_SCREEN_COPY.loadingLabel}
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
    width: "100%",
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
  helper: {
    color: color.fgTertiary,
    fontSize: 13,
  },
  card: {
    gap: space.s12,
  },
  troubleshootingBody: {
    gap: space.s8,
  },
  troubleshootingLabel: {
    color: color.fgSecondary,
    fontSize: 13,
    fontWeight: "600",
  },
  troubleshootingValue: {
    color: color.fgPrimary,
    fontSize: 14,
    fontWeight: "500",
  },
  troubleshootingStep: {
    color: color.fgSecondary,
    fontSize: 13,
    lineHeight: 19,
  },
});
