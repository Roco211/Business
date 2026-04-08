import { FRONTLINE_STATUS_COPY } from "../copy/frontlineStatus";
import { SessionStreamConnectionState } from "./sessionStreamClient";

type GetWorkbenchConnectionCopyInput = {
  bootstrapError: string | null;
  connectionState: SessionStreamConnectionState;
};

type WorkbenchConnectionCopy = {
  title: string;
  hint: string;
  actionLabel?: string;
};

const NETWORK_BOOTSTRAP_ERROR_PATTERN =
  /(network request failed|failed to fetch|fetch failed|cannot reach api|econnrefused|timeout|timed out)/i;

export function getWorkbenchConnectionCopy(
  input: GetWorkbenchConnectionCopyInput,
): WorkbenchConnectionCopy {
  if (input.bootstrapError) {
    const isNetworkBootstrapError = NETWORK_BOOTSTRAP_ERROR_PATTERN.test(input.bootstrapError);
    return {
      title: "\u5de5\u4f5c\u53f0\u6682\u65f6\u4e0d\u53ef\u7528",
      hint: isNetworkBootstrapError
        ? FRONTLINE_STATUS_COPY.networkUnavailable
        : FRONTLINE_STATUS_COPY.workbenchUnavailable,
      actionLabel: "\u91cd\u8bd5\u8fde\u63a5",
    };
  }

  if (input.connectionState === "connected") {
    return {
      title: "\u5df2\u8fde\u63a5",
      hint: "\u5b9e\u65f6\u66f4\u65b0\u6b63\u5e38\u3002",
    };
  }

  if (input.connectionState === "connecting" || input.connectionState === "bootstrapping") {
    return {
      title: "\u6b63\u5728\u8fde\u63a5",
      hint: "\u6b63\u5728\u540c\u6b65\u4f1a\u8bdd\u4e0e\u5b9e\u65f6\u66f4\u65b0\u3002",
    };
  }

  if (input.connectionState === "disconnected" || input.connectionState === "error") {
    return {
      title: "\u8fde\u63a5\u53d7\u9650",
      hint: "\u63d0\u4ea4\u4ecd\u53ef\u7ee7\u7eed\uff0c\u4f46\u7ed3\u679c\u5237\u65b0\u53ef\u80fd\u5ef6\u8fdf\u3002",
      actionLabel: "\u7acb\u5373\u5237\u65b0",
    };
  }

  return {
    title: "\u7b49\u5f85\u8fde\u63a5",
    hint: "\u8bf7\u7a0d\u5019\uff0c\u5de5\u4f5c\u53f0\u6b63\u5728\u51c6\u5907\u4e2d\u3002",
  };
}
