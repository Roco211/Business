export type WorkbenchIntent =
  | "voice-query"
  | "photo-stock-in"
  | "receipt-entry"
  | "pending-confirmations";

export const WORKBENCH_INTENT_COPY: Record<
  WorkbenchIntent,
  { dashboardLabel: string; dashboardDetail: string; workbenchTitle: string; workbenchHint: string }
> = {
  "voice-query": {
    dashboardLabel: "语音查货",
    dashboardDetail: "一句话查看库存和缺货风险",
    workbenchTitle: "从这里发起语音查货",
    workbenchHint: "语音入口会高亮，你可以直接开始。",
  },
  "photo-stock-in": {
    dashboardLabel: "拍照入库",
    dashboardDetail: "对着商品拍照后继续确认",
    workbenchTitle: "从这里发起拍照入库",
    workbenchHint: "拍照入口会高亮，提交后再查看处理结果。",
  },
  "receipt-entry": {
    dashboardLabel: "票据识别",
    dashboardDetail: "快速整理票据条目和金额",
    workbenchTitle: "从这里发起票据识别",
    workbenchHint: "票据入口会高亮，提交后优先关注待确认结果。",
  },
  "pending-confirmations": {
    dashboardLabel: "待处理确认",
    dashboardDetail: "集中处理待复核事项",
    workbenchTitle: "优先处理待确认事项",
    workbenchHint: "工作台会将你带到待确认区域。",
  },
};
