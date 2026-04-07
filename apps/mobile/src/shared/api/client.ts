import { NativeModules, Platform } from "react-native";

import { clearAuthSession, getAccessToken } from "../auth/authStore";
import { resolveApiBaseUrl } from "./resolveApiBaseUrl";

type ApiRequestOptions = {
  requiresAuth?: boolean;
};


export function getApiBaseUrl(): string {
  const scriptURL =
    typeof NativeModules.SourceCode?.scriptURL === "string" ? NativeModules.SourceCode.scriptURL : null;

  return resolveApiBaseUrl({
    configuredBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL,
    platform: Platform.OS === "android" ? "android" : "ios",
    scriptURL,
  });
}

function buildAuthHeader(options?: ApiRequestOptions): Record<string, string> {
  if (options?.requiresAuth === false) {
    return {};
  }

  const accessToken = getAccessToken();
  if (accessToken === null) {
    return {};
  }

  return {
    Authorization: `Bearer ${accessToken}`,
  };
}

function handleUnauthorized(responseStatus: number, options?: ApiRequestOptions) {
  if (responseStatus === 401 && options?.requiresAuth !== false) {
    clearAuthSession();
  }
}


export async function apiGetJson<T>(path: string, options?: ApiRequestOptions): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    headers: buildAuthHeader(options),
  });
  const payload = await response.json();
  if (!response.ok) {
    handleUnauthorized(response.status, options);
    throw new Error(payload?.error?.message ?? "Request failed");
  }
  return payload as T;
}


export async function apiPostJson<TResponse, TBody>(
  path: string,
  body: TBody,
  options?: ApiRequestOptions,
): Promise<TResponse> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeader(options),
    },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) {
    handleUnauthorized(response.status, options);
    throw new Error(payload?.error?.message ?? "Request failed");
  }
  return payload as TResponse;
}
