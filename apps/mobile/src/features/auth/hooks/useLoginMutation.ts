import { useState } from "react";

import { apiPostJson } from "../../../shared/api/client";
import { useAuth } from "../../../shared/auth/AuthProvider";
import { getFriendlyStatusMessage } from "../../../shared/copy/getFriendlyStatusMessage";

type LoginResponse = {
  data: {
    access_token: string;
    token_type: string;
    owner_actor_id: string;
    shop_id: string;
    shop_name: string;
  };
};

type LoginRequest = {
  email: string;
  password: string;
};

export function useLoginMutation() {
  const auth = useAuth();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submitLogin(email: string, password: string) {
    const trimmedEmail = email.trim();
    const hasNonWhitespacePassword = password.trim().length > 0;

    if (trimmedEmail.length === 0 || !hasNonWhitespacePassword) {
      setError("请输入邮箱和密码。");
      return false;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await apiPostJson<LoginResponse, LoginRequest>(
        "/api/v1/auth/login",
        {
          email: trimmedEmail,
          password,
        },
        { requiresAuth: false },
      );

      auth.login({
        accessToken: response.data.access_token,
        tokenType: response.data.token_type,
        ownerActorId: response.data.owner_actor_id,
        shopId: response.data.shop_id,
        shopName: response.data.shop_name,
      });

      return true;
    } catch (reason: unknown) {
      setError(
        getFriendlyStatusMessage(
          reason instanceof Error ? reason.message : null,
          "登录暂时不可用，请稍后再试。",
        ),
      );
      return false;
    } finally {
      setIsSubmitting(false);
    }
  }

  return {
    isSubmitting,
    error,
    submitLogin,
  };
}
