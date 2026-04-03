# showcase_app

这是一个基于 FastAPI 的项目介绍站，用来把当前产品、技术方案、用户旅程和可优化点通过 Web 页面展示出来。

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

说明：

- `main.py` 现在支持直接启动
- 这种方式默认不启用热重载，稳定性更高
- 推荐优先把依赖安装到当前 Python 环境，而不是依赖项目内的临时下载目录

启动后访问：

```text
http://127.0.0.1:8000
```

也支持使用 uvicorn 启动：

```bash
uvicorn showcase_app.main:app --reload
```

## 页面内容

- 产品定位与价值
- 用户使用旅程
- 三主页面和六条主链路
- FastAPI 后端架构角色
- 核心 API 与数据模型
- `project_docs` 文档地图
- 下一步优化清单

## 接口

- `/` 项目介绍页
- `/api/overview` 项目摘要 JSON
- `/health` 健康检查
