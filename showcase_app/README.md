# showcase_app

这是一个基于 FastAPI 的“原型总控台”，它把 `project_docs` 里的产品、架构、AI 员工、接口、数据模型、风险与交付节奏，重新组织成一张可以从上帝视角审视原型的展示页。

## 启动方式

推荐在项目根目录执行：

```bash
pip install -r requirements.txt
python showcase_app/main.py
```

如果你已经进入 `showcase_app` 目录，也可以直接：

```bash
python .\main.py
```

启动后访问：

```text
http://127.0.0.1:8000
```

也支持使用 uvicorn：

```bash
uvicorn showcase_app.main:app --reload
```

## 页面现在包含什么

- 原型判词与总览指标
- 审视镜头与四层上帝视角拆解
- 三主页面、六条主链路、客户端状态边界
- 技术栈、RN 工程蓝图、系统分层与职责边界
- AI 员工合同、内部 Runtime Loop、Claw 启发与权限模型
- API 合同、核心 schema、存储建议与一致性铁律
- Sprint 路线图、风险、关键决策、最小 Demo 范围
- 工作区真实现状与 `project_docs` 文档索引

## 接口

- `/` 原型总控台
- `/api/overview` 项目摘要 JSON
- `/health` 健康检查
