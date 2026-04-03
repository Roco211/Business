# AI数字店铺大管家 - 开发蓝图索引

这套文档把当前 PRD 和原型拆成可开发的 React Native 首版方案。

已选定的基础假设：

- 首版客户端使用 `React Native + TypeScript`
- 使用 `Expo Managed + EAS`
- 后端使用 `FastAPI + MySQL`
- 语音、多模态、OCR 都通过服务端编排
- 客户端负责采集、上传、展示、确认和回执

推荐阅读顺序：

1. [00-final-tech-stack.md](./00-final-tech-stack.md)
2. [01-react-native-architecture.md](./01-react-native-architecture.md)
3. [02-api-contract.md](./02-api-contract.md)
4. [03-data-models.md](./03-data-models.md)
5. [04-client-state-and-flows.md](./04-client-state-and-flows.md)
6. [05-sprint-plan.md](./05-sprint-plan.md)
7. [06-risks-and-decisions.md](./06-risks-and-decisions.md)

文档用途：

- `00` 解决“最终栈到底定了什么”
- `01` 解决“项目怎么搭”
- `02` 解决“接口怎么定”
- `03` 解决“数据怎么存”
- `04` 解决“页面和状态怎么跑”
- `05` 解决“开发怎么排期”
- `06` 解决“首版有哪些关键取舍”

本目录不替代 PRD。

- `AI_Store_Manager_PRD.md` 继续负责产品目标和范围
- `project_docs/*` 负责工程落地
