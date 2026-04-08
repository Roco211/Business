import { normalizeRuntimeMessage } from "../../../shared/copy/frontlineStatus";

const MOCK_RUNTIME_PREFIX_PATTERN = /^mock runtime:\s*/i;

type PresentRuntimeMessageTextOptions = {
  isRuntimeSystemMessage?: boolean;
};

export function presentRuntimeMessageText(
  text: string,
  options: PresentRuntimeMessageTextOptions = {},
) {
  if (!options.isRuntimeSystemMessage) {
    return text;
  }

  const normalizedText = normalizeRuntimeMessage(text);

  if (!MOCK_RUNTIME_PREFIX_PATTERN.test(normalizedText)) {
    return normalizedText;
  }

  const withoutPrefix = normalizedText.replace(MOCK_RUNTIME_PREFIX_PATTERN, "").trim();
  return withoutPrefix;
}
