export const FRONTLINE_STATUS_COPY = {
  networkUnavailable: "当前无法连接门店服务，请检查网络后重试。",
  loginUnavailable: "登录暂时不可用，请稍后再试。",
  workbenchUnavailable: "工作台暂时不可用，请稍后再试。",
  taskFailed: "任务处理失败，请稍后再试。",
  realtimeDegraded: "实时更新受限，执行操作后仍会触发手动刷新。",
} as const;

const MOCK_RUNTIME_STOCK_QUERY_ACCEPTED_PATTERN = /mock runtime:\s*stock query accepted/i;
const MOCK_RUNTIME_TASK_FAILED_PATTERN = /mock runtime could not process this task/i;

export function normalizeRuntimeMessage(message: string) {
  if (MOCK_RUNTIME_STOCK_QUERY_ACCEPTED_PATTERN.test(message)) {
    return FRONTLINE_STATUS_COPY.realtimeDegraded;
  }

  if (MOCK_RUNTIME_TASK_FAILED_PATTERN.test(message)) {
    return FRONTLINE_STATUS_COPY.taskFailed;
  }

  return message;
}
