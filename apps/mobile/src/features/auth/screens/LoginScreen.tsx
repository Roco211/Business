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
  brandName: "门店助理",
  brandTagline: "轻松看店、理货、记账",
  heroIntro: "先看店铺概览，再处理今天的门店事项。",
  cardTitle: "进入当前门店",
  cardSubtitle: "当前测试环境使用邮箱登录，连接异常时会在下方直接提示。",
  emailLabel: "邮箱",
  passwordLabel: "密码",
  passwordPlaceholder: "请输入密码",
  loginLabel: "进入门店助理",
  loadingLabel: "正在进入...",
  loginErrorTitle: "暂时无法进入",
  loginErrorFallback: "登录暂时不可用，请稍后再试。",
  troubleshootingTitle: "连接排查",
  currentServiceLabel: "当前门店服务",
  stepCheckService: "检查本机或门店服务是否已启动",
  stepAndroidEmulator: "若在安卓模拟器中运行，请确认后端使用 10.0.2.2",
  stepDeviceNetwork: "若是真机测试，请确保设备与开发机在同一网络",
  helper: "如果页面提示连接异常，请检查网络后稍后再试。",
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
          <View style={styles.brandHero}>
            <View style={styles.brandMark}>
              <Text style={styles.brandMarkText}>S</Text>
            </View>
            <Text style={styles.brandName}>{LOGIN_SCREEN_COPY.brandName}</Text>
            <Text style={styles.brandTagline}>{LOGIN_SCREEN_COPY.brandTagline}</Text>
            <Text style={styles.heroIntro}>{LOGIN_SCREEN_COPY.heroIntro}</Text>
          </View>
          <SurfaceCard emphasis="elevated" style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle}>{LOGIN_SCREEN_COPY.cardTitle}</Text>
              <Text style={styles.cardSubtitle}>{LOGIN_SCREEN_COPY.cardSubtitle}</Text>
            </View>
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
                    {`• ${step}`}
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
          <Text style={styles.helper}>{LOGIN_SCREEN_COPY.helper}</Text>
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
  brandHero: {
    alignItems: "center",
    gap: space.s8,
    marginBottom: space.s20,
    paddingHorizontal: space.s12,
  },
  brandMark: {
    alignItems: "center",
    backgroundColor: color.bgBrandSoft,
    borderRadius: 28,
    height: 72,
    justifyContent: "center",
    marginBottom: space.s12,
    width: 72,
  },
  brandMarkText: {
    color: color.accentPrimary,
    fontSize: 32,
    fontWeight: "700",
  },
  brandName: {
    color: color.fgPrimary,
    fontSize: 34,
    fontWeight: "700",
    letterSpacing: -0.8,
  },
  brandTagline: {
    color: color.fgSecondary,
    fontSize: 18,
  },
  heroIntro: {
    color: color.fgSecondary,
    fontSize: 15,
    lineHeight: 22,
    textAlign: "center",
  },
  card: {
    gap: space.s12,
    paddingVertical: space.s20,
  },
  cardHeader: {
    gap: 6,
  },
  cardTitle: {
    color: color.fgPrimary,
    fontSize: 22,
    fontWeight: "700",
    letterSpacing: -0.4,
  },
  cardSubtitle: {
    color: color.fgSecondary,
    fontSize: 14,
    lineHeight: 20,
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
  helper: {
    color: color.fgTertiary,
    fontSize: 13,
    lineHeight: 19,
    marginTop: space.s12,
    textAlign: "center",
  },
});
