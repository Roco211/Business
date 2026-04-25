# Phase J1 AI任务执行复盘

## 背景

Phase I 已完成 AI Command Center、AI员工真实状态、AI Task Flow、三类 AI 草稿闭环和经营参谋日报。进入商用试运行体验打磨后，老板点击“确认并执行”后需要立刻知道 AI 到底执行了什么、影响了哪些业务事实，否则任务消失会削弱信任感。

## 目标

- [x] 审批 API 对确定性落账任务返回 `resolution_payload.execution_result`。
- [x] execution_result 包含执行状态、业务对象、复盘摘要、影响模块和下一步路由。
- [x] 覆盖销售单草稿审批和采购草稿审批的后端回归。
- [x] 库存入库/出库审批也写入库存流水执行复盘。
- [x] H5 任务中心点击确认后展示“刚刚完成的AI执行复盘”。
- [x] 保持 confirmation-first：复盘只在审批成功并真实落账后生成。
- [x] focused 后端测试通过。
- [x] H5 build 通过。
- [x] Docker 8001 热更新并浏览器验收执行复盘。
- [x] git diff/status 检查，只提交 J1 相关文件。
- [x] commit + push。

## 安全边界

- 执行复盘不是新的写入口，不绕过审批。
- AI 仍不能直接修改业务真相；必须先 pending confirmation。
- 复盘来源于审批服务实际落账结果，不由前端伪造。
- 不输出 token、API key、数据库连接串等敏感信息。

## 验收口径

- 后端审批销售/采购草稿后，响应里包含 `execution_result.status == committed`。
- H5 任务中心确认任务后出现“刚刚完成的AI执行复盘”。
- 页面无横向溢出，浏览器 console errors 为 0。
