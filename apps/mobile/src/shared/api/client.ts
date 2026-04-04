import { Platform } from "react-native";


const DEFAULT_OWNER_TOKEN = "mock_owner_token";


function getBaseUrl(): string {
  const configuredBaseUrl = process.env.EXPO_PUBLIC_API_BASE_URL?.trim();
  if (configuredBaseUrl) {
    return configuredBaseUrl.replace(/\/+$/, "");
  }
  return Platform.OS === "android" ? "http://10.0.2.2:8001" : "http://127.0.0.1:8001";
}


export async function apiGetJson<T>(path: string): Promise<T> {
  const response = await fetch(`${getBaseUrl()}${path}`, {
    headers: {
      Authorization: `Bearer ${DEFAULT_OWNER_TOKEN}`,
    },
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.error?.message ?? "Request failed");
  }
  return payload as T;
}
