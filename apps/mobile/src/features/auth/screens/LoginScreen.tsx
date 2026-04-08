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
            <Text style={styles.kicker}>门店试运行</Text>
            <Text style={styles.title}>先确认连接，再开始今日入库</Text>
            <Text style={styles.subtitle}>登录后即可继续语音、拍照和票据入账</Text>
            <Text style={styles.helper}>环境地址仅供排查，日常可直接登录。</Text>
          </View>
          <SurfaceCard emphasis="outlined" style={styles.card}>
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
                title="暂时无法登录"
                message={getFriendlyStatusMessage(login.error, "登录暂时不可用，请稍后再试。")}
              />
            ) : null}
            <PrimaryButton
              label="登录"
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
});
