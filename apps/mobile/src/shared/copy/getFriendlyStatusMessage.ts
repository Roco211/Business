import { FRONTLINE_STATUS_COPY, normalizeRuntimeMessage } from "./frontlineStatus";

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

  const normalizedMessage = normalizeRuntimeMessage(trimmedMessage);

  if (CHINESE_CHARACTER_PATTERN.test(normalizedMessage)) {
    return normalizedMessage;
  }

  if (NETWORK_ERROR_PATTERN.test(normalizedMessage)) {
    return FRONTLINE_STATUS_COPY.networkUnavailable;
  }

  return normalizedMessage;
}
