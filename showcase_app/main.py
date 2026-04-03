from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


app = FastAPI(
    title="AI数字店铺大管家 - 项目介绍站",
    description="面向产品方和开发方的图文化介绍页面",
    version="0.1.0",
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


SHOWCASE_DATA = {
    "hero_tags": [
        "语音优先",
        "多模态辅助",
        "React Native",
        "FastAPI",
        "MySQL",
        "微信式工作群",
    ],
    "quick_metrics": [
        {"label": "主页面", "value": "3 个"},
        {"label": "核心链路", "value": "6 条"},
        {"label": "核心后端", "value": "FastAPI"},
        {"label": "MVP 目标", "value": "库存闭环"},
    ],
    "user_outcomes": [
        {
            "title": "老板几乎不用表单",
            "body": "最常见的动作应该是先开口说，再在必要时补一张商品图、货架图或进货单。",
        },
        {
            "title": "错误可以被确认和纠正",
            "body": "任何低置信识别、新商品建档和价格不明场景，都必须进入确认链，而不是直接写库。",
        },
        {
            "title": "体验尽量贴近微信",
            "body": "聊天页、输入方式、结果回执和操作节奏都尽量靠近微信群聊，以降低学习成本。",
        },
    ],
    "screen_cards": [
        {
            "name": "工作台",
            "goal": "老板一眼看经营状态和待确认任务",
            "highlights": [
                "明显的语音主入口",
                "低库存提醒",
                "待确认卡",
                "进入工作群和账本",
            ],
        },
        {
            "name": "工作群",
            "goal": "像微信一样发起语音、图片和单据任务",
            "highlights": [
                "语音主输入",
                "商品拍照建档",
                "拍照查询库存",
                "进货单 OCR 结果卡",
            ],
        },
        {
            "name": "账本",
            "goal": "承接最终库存真相和人工纠错",
            "highlights": [
                "库存项列表",
                "最近库存事件",
                "人工纠错表单",
                "审计时间线",
            ],
        },
    ],
    "journey_steps": [
        {"title": "语音发起", "body": "老板先说一句“今天进来 3 箱可乐”或“红牛还剩多少？”。"},
        {"title": "多模态补盲", "body": "如果信息不够，系统会自然要求补一张商品图、货架图或进货单。"},
        {"title": "FastAPI 编排", "body": "FastAPI 统一承接请求，再把 ASR、识图、OCR、库存工具和确认链串起来。"},
        {"title": "结果回写", "body": "结果卡回到工作群；关键写操作会同步到账本和审计时间线。"},
    ],
    "backend_roles": [
        {"title": "FastAPI API 层", "body": "暴露 REST API 与 WebSocket，承接移动端语音、图片、单据和确认请求。"},
        {"title": "任务编排层", "body": "统一生成 TaskRun、Confirmation、InventoryEvent 和 AuditLog，不让模型直接写业务真相。"},
        {"title": "Celery + Redis", "body": "处理较重的语音转写、商品识别、OCR 抽取和结果卡生成任务。"},
        {"title": "MySQL + SQLAlchemy", "body": "承接结构化业务数据：商品、库存、会话索引、确认链和审计链。"},
        {"title": "MinIO", "body": "存放语音录音、商品图片和进货单图片，数据库只保存媒体元数据和引用。"},
    ],
    "api_groups": [
        {"name": "会话与消息", "items": ["POST /api/v1/sessions/bootstrap", "GET /api/v1/sessions/:id/messages", "POST /api/v1/sessions/:id/messages"]},
        {"name": "媒体与多模态", "items": ["POST /api/v1/media-uploads", "POST /api/v1/ocr-documents", "GET /api/v1/ocr-documents/:id", "POST /api/v1/inventory-items/recognize-and-query"]},
        {"name": "库存与纠错", "items": ["GET /api/v1/inventory-items", "GET /api/v1/alerts?type=low-stock", "POST /api/v1/confirmations/:id/approve", "POST /api/v1/inventory-events/corrections"]},
    ],
    "data_models": [
        "ConversationSession",
        "SessionMessage",
        "TaskRun",
        "InventoryItem",
        "InventoryEvent",
        "Confirmation",
        "OcrDocument",
        "Alert",
        "AuditLog",
    ],
    "docs_index": [
        {"path": "project_docs/00-final-tech-stack.md", "summary": "当前 MVP 的最终技术选型，包括 React Native、FastAPI、MySQL、Celery、Redis、MinIO。"},
        {"path": "project_docs/01-react-native-architecture.md", "summary": "客户端架构、模块边界、导航方式和 FastAPI 编排链路。"},
        {"path": "project_docs/02-api-contract.md", "summary": "REST API 合同草案，覆盖会话、媒体、多模态、确认和纠错。"},
        {"path": "project_docs/03-data-models.md", "summary": "服务端和客户端的统一数据对象定义。"},
        {"path": "project_docs/04-client-state-and-flows.md", "summary": "三主页面和六条主链路的客户端状态与流程。"},
        {"path": "project_docs/05-sprint-plan.md", "summary": "从工程基础到多模态补盲、确认与账本的开发拆解。"},
    ],
    "optimize_points": [
        {"title": "语音主入口够不够强", "body": "打开首页时，用户是否一秒钟就能感知“这个 App 是可以直接说话操作的”？"},
        {"title": "聊天页够不够像微信", "body": "群聊节奏、输入区、消息气泡和结果卡是否已经足够接近日常使用习惯？"},
        {"title": "多模态是否只是展示，不是真帮助", "body": "拍照建档、拍照查询和进货单 OCR 是否真正补齐了语音无法表达的信息缺口？"},
        {"title": "确认链是否过重或过轻", "body": "哪些地方必须确认，哪些地方可以自动做，需要继续精调，避免让用户觉得繁琐或不安全。"},
        {"title": "账本是否足够清晰", "body": "当 AI 出错时，账本和审计时间线是否足够直观，让老板愿意亲自修正而不是放弃使用？"},
        {"title": "FastAPI 后端边界是否合理", "body": "哪些任务必须走 API 同步返回，哪些更适合走 Celery 异步处理，仍值得进一步压测和微调。"},
    ],
}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, **SHOWCASE_DATA})


@app.get("/api/overview")
async def overview():
    return {
        "project": "AI数字店铺大管家",
        "frontend": "React Native + Expo",
        "backend": "FastAPI + MySQL",
        "positioning": "语音优先、多模态辅助的库存协同副驾",
        "core_flows": ["语音入库", "语音查询", "拍照建档", "拍照查询", "进货单 OCR", "人工纠错"],
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
    )
