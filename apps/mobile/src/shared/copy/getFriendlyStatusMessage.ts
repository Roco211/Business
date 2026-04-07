const CHINESE_CHARACTER_PATTERN = /[\u3400-\u9fff]/;
const NETWORK_ERROR_PATTERN =
  /(network request failed|failed to fetch|fetch failed|cannot reach api|econnrefused|timeout|timed out)/i;

export function getFriendlyStatusMessage(
  message: string | null | undefined,
  fallbackMessage: string,
) {
  const trimmedMessage = message?.trim();

  if (!trimmedMessage) {
    return fallbackMessage;
  }

  if (CHINESE_CHARACTER_PATTERN.test(trimmedMessage)) {
    return trimmedMessage;
  }

  if (NETWORK_ERROR_PATTERN.test(trimmedMessage)) {
    return "当前无法连接门店服务，请检查网络后重试。";
  }

  return trimmedMessage;
}
