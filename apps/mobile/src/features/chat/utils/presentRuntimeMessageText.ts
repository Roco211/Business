import { normalizeRuntimeMessage } from "../../../shared/copy/frontlineStatus";

const MOCK_RUNTIME_PREFIX_PATTERN = /^mock runtime:\s*/i;

export function presentRuntimeMessageText(text: string) {
  const normalizedText = normalizeRuntimeMessage(text);

  if (!MOCK_RUNTIME_PREFIX_PATTERN.test(normalizedText)) {
    return normalizedText;
  }

  const withoutPrefix = normalizedText.replace(MOCK_RUNTIME_PREFIX_PATTERN, "").trim();
  if (withoutPrefix.length > 0) {
    return withoutPrefix;
  }

  return normalizedText.trim();
}
