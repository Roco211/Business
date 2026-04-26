# Phase L3 + L4：H5 设计系统统一与普通用户界面产品化

## 背景

用户反馈当前 Business H5 体验仍有明显问题：

1. 页面有拼装感，部分表单/按钮/卡片不统一。
2. 普通老板用户会看到大量开发期文本、接口路径、阶段编号、技术验收词。
3. Dashboard 已完成 AI-first 入口，Chat 已接真实 LLM，但整体产品界面仍需要更像可试用产品，而不是工程验收面板。

## 目标

L3：统一主要 H5 视觉语言，减少裸控件/错位/拼装感。

L4：隐藏普通用户路径中的开发期与技术诊断入口，把诊断能力迁移到 owner 可见的高级入口。

## 本阶段范围

- 普通左侧导航不再直接展示“试运行验收”。
- owner 顶部提供“系统诊断”高级入口；clerk/finance 看不到。
- AccessDenied 改为产品化权限提示，不暴露 RBAC、前端/后端强制校验等工程术语。
- 试运行/商用硬化页面改为高级诊断页，仅 owner 可达，文案尽量产品化。
- 对主要输入框、按钮、表格、卡片增加统一设计兜底样式，减少裸控件。
- 保留真实商用边界，不伪造数据。

## 不做

- 不改后端业务真相模型。
- 不接真实短信。
- 不拆分前端组件目录，避免在单文件阶段引入大重构风险。
- 不输出任何 `.env`、token、API Key 或连接串。

## 验收标准

1. 前端扫描测试通过：普通导航不出现试运行验收、K1/K2、Phase、readiness、preflight、Docker、Redis、PostgreSQL 等技术词。
2. owner 高级诊断入口存在，且由 roleKey === 'owner' 控制。
3. AccessDenied 文案不出现 RBAC、前端、后端、接口等开发术语。
4. H5 build 通过。
5. 浏览器访问 8001，普通路径 Dashboard/AI/商品/库存无 console error。
6. Docker 热更新后仍能登录并看到 AI-first Dashboard。
7. 提交并推送到 `origin/hermes/ai-native-saas-rewrite`。
