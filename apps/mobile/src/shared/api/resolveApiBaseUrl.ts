type ResolveApiBaseUrlInput = {
  configuredBaseUrl: string | null | undefined;
  platform: "android" | "ios";
  scriptURL: string | null | undefined;
};

export function inferDevServerHost(scriptURL: string | null | undefined): string | null {
  if (!scriptURL) {
    return null;
  }

  try {
    return new URL(scriptURL).hostname || null;
  } catch {
    return null;
  }
}

export function resolveApiBaseUrl(input: ResolveApiBaseUrlInput): string {
  const configuredBaseUrl = input.configuredBaseUrl?.trim();
  if (configuredBaseUrl) {
    return configuredBaseUrl.replace(/\/+$/, "");
  }

  const inferredDevServerHost = inferDevServerHost(input.scriptURL);
  if (inferredDevServerHost) {
    return `http://${inferredDevServerHost}:8001`;
  }

  return input.platform === "android" ? "http://10.0.2.2:8001" : "http://127.0.0.1:8001";
}
