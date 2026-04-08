export type WorkbenchIntent =
  | "voice-query"
  | "photo-stock-in"
  | "receipt-entry"
  | "pending-confirmations";

export const WORKBENCH_INTENT_COPY: Record<
  WorkbenchIntent,
  { dashboardLabel: string; workbenchTitle: string; workbenchHint: string }
> = {
  "voice-query": {
    dashboardLabel: "语音查货",
    workbenchTitle: "从这里发起语音查货",
    workbenchHint: "语音路径会被高亮，你可以直接开始。",
  },
  "photo-stock-in": {
    dashboardLabel: "拍照入库",
    workbenchTitle: "从这里发起拍照入库",
    workbenchHint: "拍照路径会被高亮，提交后再查看结果。",
  },
  "receipt-entry": {
    dashboardLabel: "票据识别",
    workbenchTitle: "从这里发起票据识别",
    workbenchHint: "票据路径会被高亮，提交后优先关注待确认。",
  },
  "pending-confirmations": {
    dashboardLabel: "待确认",
    workbenchTitle: "优先处理待确认",
    workbenchHint: "工作台会将你带到待确认区域。",
  },
};
