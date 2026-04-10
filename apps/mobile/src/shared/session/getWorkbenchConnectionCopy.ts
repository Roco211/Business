import { FRONTLINE_STATUS_COPY } from "../copy/frontlineStatus";
import { SessionStreamConnectionState } from "./sessionStreamClient";

type GetWorkbenchConnectionCopyInput = {
  bootstrapError: string | null;
  connectionState: SessionStreamConnectionState;
};

type WorkbenchConnectionCopy = {
  title: string;
  hint: string;
};

const NETWORK_BOOTSTRAP_ERROR_PATTERN =
  /(network request failed|failed to fetch|fetch failed|cannot reach api|econnrefused|timeout|timed out)/i;

export function getWorkbenchConnectionCopy(
  input: GetWorkbenchConnectionCopyInput,
): WorkbenchConnectionCopy {
  if (input.bootstrapError) {
    const isNetworkBootstrapError = NETWORK_BOOTSTRAP_ERROR_PATTERN.test(input.bootstrapError);
    return {
      title: "工作台暂时不可用",
      hint: isNetworkBootstrapError
        ? FRONTLINE_STATUS_COPY.networkUnavailable
        : FRONTLINE_STATUS_COPY.workbenchUnavailable,
    };
  }

  if (input.connectionState === "connected") {
    return {
      title: "已连接",
      hint: "实时更新正常。",
    };
  }

  if (input.connectionState === "connecting" || input.connectionState === "bootstrapping") {
    return {
      title: "正在连接",
      hint: "正在同步会话与实时更新。",
    };
  }

  if (input.connectionState === "disconnected" || input.connectionState === "error") {
    return {
      title: "连接受限",
      hint: FRONTLINE_STATUS_COPY.realtimeDegraded,
    };
  }

  return {
    title: "等待连接",
    hint: "请稍候，工作台正在准备中。",
  };
}
