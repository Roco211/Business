type ResolveApiBaseUrlInput = {
  configuredBaseUrl: string | null | undefined;
  platform: "android" | "ios";
  scriptURL: string | null | undefined;
  runtimeHostUri?: string | null | undefined;
};

function isLoopbackHost(host: string): boolean {
  const normalizedHost = host.toLowerCase();
  return (
    normalizedHost === "localhost"
    || normalizedHost === "127.0.0.1"
    || normalizedHost.startsWith("127.")
    || normalizedHost === "::1"
    || normalizedHost === "[::1]"
  );
}

export function inferDevServerHost(scriptURL: string | null | undefined): string | null {
  const trimmedValue = scriptURL?.trim();
  if (!trimmedValue) {
    return null;
  }

  try {
    return new URL(trimmedValue).hostname || null;
  } catch {
    try {
      return new URL(`http://${trimmedValue}`).hostname || null;
    } catch {
      return null;
    }
  }
}

function resolveDevServerHost(
  scriptURL: string | null | undefined,
  runtimeHostUri: string | null | undefined,
): string | null {
  return inferDevServerHost(scriptURL) ?? inferDevServerHost(runtimeHostUri);
}

export function resolveApiBaseUrl(input: ResolveApiBaseUrlInput): string {
  const configuredBaseUrl = input.configuredBaseUrl?.trim();
  if (configuredBaseUrl) {
    return configuredBaseUrl.replace(/\/+$/, "");
  }

  const inferredDevServerHost = resolveDevServerHost(input.scriptURL, input.runtimeHostUri);
  if (inferredDevServerHost && !(input.platform === "android" && isLoopbackHost(inferredDevServerHost))) {
    return `http://${inferredDevServerHost}:8001`;
  }

  return input.platform === "android" ? "http://10.0.2.2:8001" : "http://127.0.0.1:8001";
}
