import type { WorkbenchIntent } from "../../features/chat/workbenchIntent";

export const ROOT_TABS = {
  dashboard: "dashboard",
  workbench: "workbench",
  ledger: "ledger",
} as const;

export type RootTabParamList = {
  dashboard: undefined;
  workbench: { initialIntent?: WorkbenchIntent } | undefined;
  ledger: undefined;
};

export const ROOT_TAB_LABELS: Record<keyof RootTabParamList, string> = {
  dashboard: "首页",
  workbench: "工作台",
  ledger: "台账",
};
