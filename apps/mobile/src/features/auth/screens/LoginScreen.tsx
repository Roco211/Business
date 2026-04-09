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
          <View style={styles.brandHero}>
            <View style={styles.brandMark}>
              <Text style={styles.brandMarkText}>S</Text>
            </View>
            <Text style={styles.brandName}>门店助理</Text>
            <Text style={styles.brandTagline}>轻松看店、理货、记账</Text>
            <Text style={styles.heroIntro}>先看店铺概览，再处理今天的门店事项。</Text>
          </View>
          <SurfaceCard emphasis="elevated" style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle}>进入当前门店</Text>
              <Text style={styles.cardSubtitle}>
                当前测试环境使用邮箱登录，连接异常时会在下方直接提示。
              </Text>
            </View>
            <AppTextField
              label="邮箱"
              autoCapitalize="none"
              keyboardType="email-address"
              onChangeText={setEmail}
              placeholder="owner@example.com"
              value={email}
            />
            <AppTextField
              label="密码"
              onChangeText={setPassword}
              placeholder="请输入密码"
              secureTextEntry
              value={password}
            />
            {login.error ? (
              <InlineNotice
                tone="error"
                title="暂时无法进入"
                message={getFriendlyStatusMessage(login.error, "登录暂时不可用，请稍后再试。")}
              />
            ) : null}
            <PrimaryButton
              label="进入门店助理"
              loading={login.isSubmitting}
              loadingLabel="正在进入..."
              onPress={() => void login.submitLogin(email, password)}
            />
          </SurfaceCard>
          <Text style={styles.helper}>如果页面提示连接异常，请检查网络后稍后再试。</Text>
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
  helper: {
    color: color.fgTertiary,
    fontSize: 13,
    lineHeight: 19,
    marginTop: space.s12,
    textAlign: "center",
  },
});
