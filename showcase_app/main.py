from pathlib import Path
from textwrap import dedent

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


BASE_DIR = Path(__file__).resolve().parent


def block(text: str) -> str:
    return dedent(text).strip()


app = FastAPI(
    title="AI数字店铺大管家 - 原型总控台",
    description="把 project_docs 重组为一张可从上帝视角审视产品、系统和交付的全局总览页。",
    version="0.4.0",
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


SHOWCASE_DATA = {
    "hero_tags": [
        "语音优先",
        "多模态补盲",
        "微信式工作群",
        "FastAPI 编排中心",
        "确认与审计",
        "AI 原生控制平面",
        "Claw 启发",
    ],
    "quick_metrics": [
        {"label": "一级页面", "value": "3", "detail": "工作台 / 工作群 / 账本"},
        {"label": "核心链路", "value": "6", "detail": "语音、拍照、OCR、纠错闭环"},
        {"label": "可见员工", "value": "2", "detail": "小雅 / 老李"},
        {"label": "内部角色", "value": "5-6", "detail": "Router 到 Summarizer"},
        {"label": "主栈", "value": "RN + FastAPI", "detail": "客户端与编排服务端双中心"},
        {"label": "施工包", "value": "14 Docs", "detail": "00-13 已覆盖到可施工层"},
    ],
    "review_lenses": [
        {
            "title": "产品定义",
            "body": "这个 MVP 不是做一个会聊天的库存工具，而是做一个老板能直接吩咐的库存协同副驾。",
        },
        {
            "title": "体验壳层",
            "body": "所有复杂能力最终都要收敛成三个主页面和微信感工作群体验，不能把后台系统感暴露给老板。",
        },
        {
            "title": "AI 控制平面",
            "body": "系统内部不是一个大模型黑箱，而是 Router、Guard、Runner、Summarizer 等角色共同完成任务。",
        },
        {
            "title": "业务真相",
            "body": "库存、审计、确认、OCR 结果都必须有结构化对象承接，模型不能直接碰业务真相。",
        },
        {
            "title": "交付路径",
            "body": "文档已经把工程拆成 Sprint 0 到 Sprint 4，重点是先跑通语音、多模态、确认与账本闭环。",
        },
        {
            "title": "原型现状",
            "body": "当前工作区里成型的是文档和介绍站，移动端、业务后端和 function calling runtime 仍是待实现蓝图。",
        },
    ],
    "god_view_panels": [
        {
            "eyebrow": "用户看到",
            "title": "老板像在微信群里指挥两个靠谱员工",
            "body": "前台体验必须足够简单，让用户主要通过语音发起任务，在必要时补图、补单据、补确认。",
            "bullets": [
                "语音是主入口",
                "图片和单据只负责补盲",
                "结果卡和确认卡说人话",
            ],
        },
        {
            "eyebrow": "体验壳层",
            "title": "三个一级页面承接全部 MVP 闭环",
            "body": "工作台负责看状态，工作群负责发任务，账本负责看真相与纠错，避免信息架构失控。",
            "bullets": [
                "DashboardScreen",
                "ChatScreen",
                "LedgerScreen",
            ],
        },
        {
            "eyebrow": "AI 控制平面",
            "title": "真正的系统内核是会话、任务、守门和工具链",
            "body": "Router 负责识别任务，Context Builder 负责补齐上下文，Policy Guard 和 Reviewer 负责卡住高风险动作。",
            "bullets": [
                "Router / Planner",
                "Context Builder",
                "Policy Guard / Reviewer",
                "Tool Runner / Summarizer",
            ],
        },
        {
            "eyebrow": "业务真相层",
            "title": "库存和审计永远要比模型聪明更重要",
            "body": "所有写操作都要经过确认、事件写入和审计记录，避免产品变成不可追溯的聊天黑箱。",
            "bullets": [
                "InventoryItem / InventoryEvent",
                "Confirmation / AuditLog",
                "Alert / OcrDocument",
            ],
        },
    ],
    "mvp_principles": [
        {
            "title": "语音是主入口",
            "body": "最常见的动作应该是老板先开口说，再在必要时补一张商品图、货架图或进货单。",
        },
        {
            "title": "多模态不是点缀",
            "body": "无码商品、货架查询和纸质进货单决定了纯语音方案不够，多模态必须进首版闭环。",
        },
        {
            "title": "系统负责落账",
            "body": "AI 负责理解，真正写入库存、确认和审计的是服务端工具链，而不是模型自由发挥。",
        },
        {
            "title": "客户端不做真相源",
            "body": "客户端只负责采集、上传、展示、确认和回执，库存真相、OCR 真相和审计真相都留在服务端。",
        },
        {
            "title": "高风险动作必须守门",
            "body": "低置信识别、新商品、缺价格、OCR 模糊字段都必须进入确认链，不能偷偷落账。",
        },
        {
            "title": "先交付，再平台化",
            "body": "首版不追求插件市场和很多员工头像，而是先把库存主链路、多模态和可追溯性做稳。",
        },
    ],
    "success_checks": [
        "工作台到工作群跳转顺畅，三主页面信息架构稳定。",
        "聊天页可承接语音、商品照片、单据照片三类输入。",
        "六条核心链路都有完整 UI 回路，而不是只停在接口或演示文案层。",
        "所有写操作都能在账本和审计时间线中回溯到来源任务。",
        "聊天状态、OCR 完成、识图完成和确认回执都能通过实时机制回写前端。",
        "用户能明显感知这是一个语音优先的协同副驾，而不是复杂 ERP。",
    ],
    "page_cards": [
        {
            "name": "工作台",
            "goal": "老板一眼看今天状态和待处理事项",
            "highlights": [
                "语音主入口必须醒目",
                "低库存提醒说人话",
                "待确认任务一目了然",
                "快速跳转工作群和账本",
            ],
        },
        {
            "name": "工作群",
            "goal": "承接语音、图片、单据任务，像微信一样自然",
            "highlights": [
                "语音主输入方式",
                "结果卡 / 确认卡 / OCR 卡",
                "拍照建档 / 拍照查询 / 进货单 OCR",
                "更像协作，而不是表单流",
            ],
        },
        {
            "name": "账本",
            "goal": "承接最终库存真相、人工纠错和审计",
            "highlights": [
                "库存项列表",
                "最近库存事件",
                "人工纠错入口简单",
                "审计时间线清晰可查",
            ],
        },
    ],
    "flow_cards": [
        {
            "name": "语音入库",
            "trigger": "老板说“今天进来 3 箱可乐”。",
            "path": ["录音", "上传音频", "ASR 与任务识别", "生成确认卡", "确认后写入 InventoryEvent"],
            "guard": "数量、单位、价格、新商品都可能触发确认。",
            "result": "聊天页返回入库结果卡，账本立即可追踪。",
        },
        {
            "name": "语音查询",
            "trigger": "老板说“红牛还剩多少？”或“这个还有没有库存？”。",
            "path": ["录音", "上传音频", "任务识别", "库存查询", "口语化结论回执"],
            "guard": "如果语音里说“这个”但缺对象，系统自然要求补图。",
            "result": "只读返回，不落账；库存低时附带补货建议。",
        },
        {
            "name": "拍照建档",
            "trigger": "老板拍一张商品照，说“这个入一下库”。",
            "path": ["拍照", "上传图片", "识图候选", "低置信进入确认", "确认后建档并入库"],
            "guard": "低置信或新商品第一次建档都不能自动写库。",
            "result": "商品档案与库存事件同时形成，流程可追踪。",
        },
        {
            "name": "拍照查询",
            "trigger": "老板对着货架或商品拍照，说“这个还有没有库存？”。",
            "path": ["拍照", "上传图片", "识图候选", "叠加库存查询", "返回商品与库存结论"],
            "guard": "识别不稳时返回候选，不允许乱答。",
            "result": "读取结果增强语音查询，不产生写操作。",
        },
        {
            "name": "进货单 OCR",
            "trigger": "老板拍一张纸质单据，说“帮我看一下这单货”。",
            "path": ["拍照单据", "上传图片", "OCR 抽字段", "低置信字段高亮", "确认后进入后续入库任务"],
            "guard": "OCR 结果本身不是库存真相，必须转成确认链。",
            "result": "输出结构化字段，而不是原始文本堆叠。",
        },
        {
            "name": "人工纠错",
            "trigger": "老板发现 AI 写错库存后手工修正。",
            "path": ["选商品", "填写目标数量与原因", "提交 correction", "刷新列表与审计"],
            "guard": "修改原因不能省略，Correction 必须是追加事件而不是覆盖。",
            "result": "账本和审计都能回溯修正来源。",
        },
    ],
    "ui_states": [
        {
            "name": "ChatUiState",
            "purpose": "承接当前会话的输入模式、录音态和媒体草稿。",
            "shape": block(
                """
                type ChatUiState = {
                  sessionId: string | null
                  inputMode: "voice" | "text"
                  toolPanelOpen: boolean
                  isRecording: boolean
                  draftMedia: LocalMediaDraft | null
                }
                """
            ),
            "notes": [
                "当前聊天输入模式",
                "工具面板是否打开",
                "本地录音与草稿媒体",
            ],
        },
        {
            "name": "TaskUiState",
            "purpose": "把会话态和任务态分开，避免消息、确认、提交混成一团。",
            "shape": block(
                """
                type TaskUiState = {
                  activeTaskRunId: string | null
                  activeConfirmationId: string | null
                  submitting: boolean
                }
                """
            ),
            "notes": [
                "当前活跃任务",
                "当前活跃确认",
                "当前是否提交中",
            ],
        },
        {
            "name": "LedgerUiState",
            "purpose": "账本侧只关注选中的商品和纠错弹层，而不侵入聊天态。",
            "shape": block(
                """
                type LedgerUiState = {
                  selectedItemId: string | null
                  correctionSheetOpen: boolean
                }
                """
            ),
            "notes": [
                "账本当前焦点商品",
                "纠错 Sheet 开关",
            ],
        },
    ],
    "screen_queries": [
        {
            "screen": "DashboardScreen",
            "items": [
                "useDashboardSummaryQuery",
                "useLowStockAlertsQuery",
                "usePendingConfirmationsQuery",
            ],
        },
        {
            "screen": "ChatScreen",
            "items": [
                "useSessionBootstrapMutation",
                "useSessionMessagesQuery",
                "useSendMessageMutation",
                "usePendingConfirmationsQuery",
            ],
        },
        {
            "screen": "LedgerScreen",
            "items": [
                "useInventoryItemsQuery",
                "useAuditLogsQuery",
                "useCreateCorrectionMutation",
            ],
        },
    ],
    "stack_columns": [
        {
            "title": "客户端",
            "summary": "围绕 React Native 和 Expo 管理采集、展示与确认。",
            "items": [
                {"name": "React Native + TypeScript", "use": "跨平台 App 与类型约束"},
                {"name": "Expo Managed + EAS", "use": "首版媒体能力接入与发版效率"},
                {"name": "React Navigation", "use": "3 主页面 + Modal / Sheet"},
                {"name": "TanStack Query", "use": "服务端状态、缓存、重试"},
                {"name": "Zustand", "use": "录音态、输入态、面板态"},
                {"name": "React Hook Form + Zod", "use": "确认卡与纠错表单"},
            ],
        },
        {
            "title": "服务端",
            "summary": "FastAPI 是编排中心，不只是接口网关。",
            "items": [
                {"name": "FastAPI", "use": "REST API、WebSocket、编排入口"},
                {"name": "SQLAlchemy 2.0 async + asyncmy", "use": "MySQL 访问层"},
                {"name": "Alembic", "use": "Schema 迁移与可追踪演进"},
                {"name": "Celery + Redis", "use": "ASR / OCR / 识图等重任务"},
                {"name": "WebSocket", "use": "聊天状态与任务回执实时推送"},
            ],
        },
        {
            "title": "基础设施",
            "summary": "围绕媒体、部署和观测性做轻量可控的 MVP 组合。",
            "items": [
                {"name": "MinIO", "use": "语音、图片、单据对象存储"},
                {"name": "Docker Compose", "use": "本地与试点环境快速编排"},
                {"name": "Mock Auth + 单店单老板", "use": "先验证产品，不先做完整账号系统"},
                {"name": "Jest + RNTL / pytest", "use": "前后端核心链路验证"},
                {"name": "结构化日志 + Sentry", "use": "低成本可观测性"},
            ],
        },
    ],
    "not_selected_tech": [
        "Bare React Native",
        "Expo Router",
        "Redux Toolkit",
        "Formik / Yup",
        "FastAPI BackgroundTasks 作为主异步框架",
        "本地磁盘存媒体",
        "轮询作为主实时策略",
        "完整手机号登录系统",
        "Kubernetes",
    ],
    "implementation_defaults": [
        {
            "title": "当前施工目标",
            "body": "这轮不是只搭壳，也不是直接接全套真实 AI，而是做一个“真实骨架 + mock AI provider”的端到端闭环。",
        },
        {
            "title": "默认实施策略",
            "body": "基础设施、数据库、WebSocket、任务编排都按真实系统搭；ASR / OCR / 识图先走 mock-first provider。",
        },
        {
            "title": "推荐落地顺序",
            "body": "先后端骨架与 runtime 合同，再接 React Native 最小壳层，避免前端先做成没有真相层的聊天皮。",
        },
    ],
    "scope_boundaries": [
        {
            "title": "当前阶段纳入范围",
            "items": [
                "默认工作群 session bootstrap",
                "媒体上传申请与消息发送",
                "voice-stock-in / voice-stock-query",
                "确认链、InventoryEvent 与 AuditLog",
                "WebSocket 实时回写",
                "后端、Worker、对象存储与 RN 骨架",
            ],
        },
        {
            "title": "当前阶段暂不纳入",
            "items": [
                "多店铺与正式账号体系",
                "多供应商并行路由",
                "流式模型输出",
                "平台化员工包 / 能力包市场",
                "复杂离线同步与实时通话",
                "开放式自由子代理",
            ],
        },
    ],
    "module_blueprint": block(
        """
        src/
          app/
            navigation/
            providers/
            bootstrap/
          features/
            dashboard/
            chat/
            inventory/
            ledger/
            media/
            ocr/
            session/
            confirmations/
          services/
            api/
            auth/
            uploads/
            analytics/
          shared/
            ui/
            utils/
            constants/
            types/
        """
    ),
    "repo_blueprint": block(
        """
        apps/
          mobile/
        backend/
          app/
            api/
            agent_runtime/
            db/
            models/
            repositories/
            services/
            workers/
            websocket/
          tests/
        infra/
          docker/
        project_docs/
        showcase_app/
        """
    ),
    "core_model_schemas": [
        {
            "name": "ConversationSession",
            "purpose": "承接老板所在的默认工作群，保证聊天入口稳定且可追溯。",
            "shape": block(
                """
                type ConversationSession = {
                  session_id: string
                  shop_id: string
                  session_type: "workgroup"
                  title: string
                  participants: string[]
                  last_message_at: string
                }
                """
            ),
        },
        {
            "name": "SessionMessage",
            "purpose": "把语音、图片、单据、结果卡、确认卡统一放进同一条消息账本。",
            "shape": block(
                """
                type SessionMessage = {
                  message_id: string
                  session_id: string
                  actor_type: "owner" | "agent" | "system"
                  actor_id: string
                  message_type:
                    | "text"
                    | "voice"
                    | "image"
                    | "receipt-image"
                    | "result-card"
                    | "confirmation-card"
                  text: string | null
                  media_ids: string[]
                  task_run_id: string | null
                  created_at: string
                }
                """
            ),
        },
        {
            "name": "TaskRun",
            "purpose": "把一次语音 / 拍照 / OCR 任务显式建模成状态机，而不是散在消息里猜。",
            "shape": block(
                """
                type TaskRun = {
                  task_run_id: string
                  session_id: string
                  task_type:
                    | "voice-stock-in"
                    | "voice-stock-query"
                    | "photo-stock-in"
                    | "photo-stock-query"
                    | "receipt-ocr"
                    | "manual-correction"
                  status:
                    | "created"
                    | "processing"
                    | "awaiting-confirmation"
                    | "completed"
                    | "rejected"
                    | "failed"
                  source_message_id: string
                  confirmation_id: string | null
                  result_summary: string | null
                  created_at: string
                  updated_at: string
                }
                """
            ),
        },
        {
            "name": "InventoryEvent",
            "purpose": "库存真相通过事件追加，不允许被聊天结果直接覆盖。",
            "shape": block(
                """
                type InventoryEvent = {
                  inventory_event_id: string
                  shop_id: string
                  item_id: string
                  event_type: "stock-in" | "stock-out" | "correction"
                  quantity_delta: number
                  quantity_after: number
                  unit: string
                  price: number | null
                  source:
                    | "voice-confirmed"
                    | "photo-confirmed"
                    | "receipt-confirmed"
                    | "manual-correction"
                  task_run_id: string | null
                  created_by: string
                  created_at: string
                }
                """
            ),
        },
        {
            "name": "Confirmation",
            "purpose": "高风险和低置信动作统一进入确认层，避免 AI 偷偷落账。",
            "shape": block(
                """
                type Confirmation = {
                  confirmation_id: string
                  task_run_id: string
                  confirmation_type:
                    | "new-item"
                    | "low-confidence-recognition"
                    | "missing-price"
                    | "quantity-review"
                    | "ocr-field-review"
                  status: "pending" | "approved" | "rejected"
                  fields: Record<string, unknown>
                  created_at: string
                  resolved_at: string | null
                }
                """
            ),
        },
        {
            "name": "OcrDocument",
            "purpose": "OCR 结果先作为辅助对象存在，不能直接冒充库存真相。",
            "shape": block(
                """
                type OcrDocument = {
                  ocr_document_id: string
                  shop_id: string
                  media_id: string
                  document_type: "purchase-receipt"
                  status: "processing" | "completed" | "failed"
                  extracted_fields: Record<string, unknown> | null
                  low_confidence_fields: string[]
                  created_at: string
                }
                """
            ),
        },
    ],
    "system_layers": [
        {
            "name": "体验层",
            "summary": "用户可见的工作台、工作群、账本、结果卡和确认卡。",
            "items": ["工作台", "工作群", "账本", "结果卡", "确认卡"],
        },
        {
            "name": "会话与任务层",
            "summary": "真正的 AI OS 壳，用 Session、Message、TaskRun、Confirmation 承接状态。",
            "items": ["ConversationSession", "SessionMessage", "TaskRun", "Confirmation"],
        },
        {
            "name": "能力编排层",
            "summary": "决定先做什么、缺什么信息、哪里要确认、哪里可以自动继续。",
            "items": [
                "Router / Planner",
                "Context Builder",
                "Policy Guard",
                "Tool Runner",
                "Reviewer",
                "Summarizer",
            ],
        },
        {
            "name": "业务真相层",
            "summary": "最终不能乱的结构化业务对象，只允许通过工具和事件写入。",
            "items": ["InventoryItem", "InventoryEvent", "AuditLog", "Alert", "OcrDocument"],
        },
    ],
    "storage_tables": [
        "shops",
        "sessions",
        "messages",
        "media_uploads",
        "task_runs",
        "inventory_items",
        "inventory_events",
        "confirmations",
        "ocr_documents",
        "alerts",
        "audit_logs",
    ],
    "index_recommendations": [
        "messages(session_id, created_at desc)",
        "messages(client_request_id)",
        "task_runs(session_id, updated_at desc)",
        "task_runs(source_message_id)",
        "inventory_items(shop_id, name)",
        "inventory_items(shop_id, barcode)",
        "inventory_events(shop_id, item_id, created_at desc)",
        "confirmations(status, created_at desc)",
        "alerts(shop_id, status, alert_type)",
        "audit_logs(shop_id, created_at desc)",
    ],
    "db_defaults": [
        {"name": "主键策略", "body": "统一用带前缀的字符串主键，建议 `prefix + ULID`，字段类型 `VARCHAR(40)`。"},
        {"name": "时间字段", "body": "统一用 `DATETIME(3)` 存 UTC，API 再按店铺时区解释。"},
        {"name": "数量与价格", "body": "库存数量用 `DECIMAL(12,3)`，价格用 `DECIMAL(12,2)`。"},
        {"name": "JSON 字段", "body": "participants、media_ids、fields、metadata 等直接用 JSON 存。"},
        {"name": "删除策略", "body": "当前 MVP 不做全局软删除，状态通过 `status` 和 `is_active` 表达。"},
    ],
    "migration_batches": [
        {"name": "Migration 001", "items": ["shops", "sessions", "media_uploads"]},
        {"name": "Migration 002", "items": ["messages", "task_runs"]},
        {"name": "Migration 003", "items": ["inventory_items", "inventory_events"]},
        {"name": "Migration 004", "items": ["confirmations", "ocr_documents", "alerts", "audit_logs"]},
    ],
    "boundary_cards": [
        {
            "title": "客户端负责",
            "items": [
                "采集语音、图片、单据",
                "上传媒体",
                "展示消息、结果卡、确认卡",
                "提交用户确认和人工纠错",
                "提供缓存、弱网重试与上传队列",
            ],
        },
        {
            "title": "服务端负责",
            "items": [
                "会话编排与模型调用",
                "ASR / OCR / 商品识别",
                "库存查询与库存事件写入",
                "风险判断、确认生成与审计记录",
                "通过 WebSocket 推送任务状态",
            ],
        },
    ],
    "claw_takeaways": [
        {
            "title": "该借的",
            "tone": "good",
            "items": [
                "Runtime loop：输入 -> 路由 -> 工具 -> 回执",
                "Tool contract：每个工具有 schema、权限和边界",
                "Role contract：员工只是一组受控能力与规则",
                "Summary / Recovery：长链路要能压缩与恢复",
            ],
        },
        {
            "title": "别直接搬的",
            "tone": "warn",
            "items": [
                "编码代理的 shell / 文件工具集",
                "Rust 本地 CLI 形态本身",
                "任意命令型插件扩展方式",
                "开放式子代理直接触碰业务真相",
            ],
        },
    ],
    "runtime_loop": [
        {"step": "Input", "body": "老板用语音、商品图或单据图发起任务。"},
        {"step": "Route", "body": "Router / Planner 识别任务类型与后续步骤。"},
        {"step": "Build Context", "body": "Context Builder 拼出店铺规则、商品、会话和最近任务上下文。"},
        {"step": "Run Tools", "body": "Tool Runner 调用 ASR、识图、OCR、库存查询等受控业务函数。"},
        {"step": "Guard", "body": "Policy Guard / Reviewer 判断能否自动继续，还是必须确认。"},
        {"step": "Confirm or Commit", "body": "低风险就回执，高风险进入确认，通过后才写 InventoryEvent 和 AuditLog。"},
        {"step": "Reply", "body": "结果卡、确认卡、聊天回执、工作台和账本统一回写。"},
    ],
    "permission_levels": [
        {"name": "read_only", "body": "只允许查库存、解释结果，不产生写操作。"},
        {"name": "needs_confirmation", "body": "新商品、低置信识别、缺价格等动作必须先进入确认链。"},
        {"name": "committable", "body": "已确认或低风险动作允许正式落账，并同步写审计。"},
        {"name": "forbidden", "body": "越界角色无权执行，即使模型主观上“觉得应该做”。"},
    ],
    "tool_specs": [
        {
            "tool": "transcribe_audio",
            "risk": "read_only",
            "roles": "小雅 / Router / ToolRunner",
            "note": "只返回文本与置信度，不直接制造业务结论。",
        },
        {
            "tool": "recognize_product",
            "risk": "read_only",
            "roles": "小雅 / 老李 / ToolRunner",
            "note": "返回候选与置信度，低置信不能直接入库。",
        },
        {
            "tool": "extract_receipt_fields",
            "risk": "read_only",
            "roles": "小雅 / 老李 / ToolRunner",
            "note": "OCR 只产生辅助字段，不等于库存真相。",
        },
        {
            "tool": "query_inventory",
            "risk": "read_only",
            "roles": "小雅 / 老李 / ToolRunner",
            "note": "查询可以直接执行，但结果仍需口语化回执。",
        },
        {
            "tool": "create_confirmation",
            "risk": "needs_confirmation",
            "roles": "小雅 / ToolRunner",
            "note": "把高风险动作显式抬到确认链。",
        },
        {
            "tool": "append_inventory_event",
            "risk": "committable",
            "roles": "老李 / ToolRunner",
            "note": "只能在已确认或低风险前提下执行。",
        },
        {
            "tool": "write_audit_log",
            "risk": "committable",
            "roles": "ToolRunner",
            "note": "业务写入完成后必须追加审计记录。",
        },
        {
            "tool": "push_session_update",
            "risk": "read_only",
            "roles": "ToolRunner / Summarizer",
            "note": "实时层负责增量回写，不承担真相存储。",
        },
    ],
    "policy_rule_cards": [
        {
            "title": "new_item_requires_confirmation",
            "body": "识别结果不存在现有商品档案时，直接转入确认态，而不是让模型帮忙脑补建档。",
        },
        {
            "title": "low_confidence_requires_confirmation",
            "body": "识图或 OCR 置信度低于店铺阈值时，系统必须要求确认。",
        },
        {
            "title": "missing_price_requires_confirmation",
            "body": "入库缺价格且店铺开启价格确认时，不允许直接写库存。",
        },
        {
            "title": "manual_correction_requires_reason",
            "body": "人工纠错没有原因就直接阻断，避免账本丢失修正上下文。",
        },
        {
            "title": "inventory_write_requires_task_run",
            "body": "任何库存写入都必须带 `task_run_id`，否则直接视为无来源写库。",
        },
        {
            "title": "very_low_confidence_escalates_review",
            "body": "极低置信时不仅要确认，还要升级到 Reviewer 做最后一层卡口。",
        },
    ],
    "task_state_transitions": [
        {"from": "created", "to": "processing", "rule": "runtime 开始处理"},
        {"from": "processing", "to": "awaiting-confirmation", "rule": "PolicyGuard 触发确认"},
        {"from": "processing", "to": "completed", "rule": "只读任务完成或低风险写入完成"},
        {"from": "processing", "to": "failed", "rule": "provider 失败、校验失败或系统异常"},
        {"from": "awaiting-confirmation", "to": "completed", "rule": "确认通过后写库成功"},
        {"from": "awaiting-confirmation", "to": "rejected", "rule": "用户拒绝确认"},
        {"from": "awaiting-confirmation", "to": "failed", "rule": "确认后提交失败或冲突"},
    ],
    "visible_agents": [
        {
            "name": "小雅",
            "role": "首席调度助理",
            "responsibilities": [
                "接收语音 / 图片 / 单据输入",
                "判断任务类型和所需补充信息",
                "决定是否转给老李",
                "决定是否生成确认卡",
                "把结果用老板能懂的话说出来",
            ],
            "must_not": [
                "直接写库存",
                "直接改价格",
                "越过确认链",
                "随意回答账本真相",
            ],
        },
        {
            "name": "老李",
            "role": "库存执行岗",
            "responsibilities": [
                "处理库存域结果",
                "整理识图和 OCR 输出",
                "生成库存结果卡和低库存建议",
                "接受确认后的正式入库动作",
            ],
            "must_not": [
                "接管所有对话",
                "做开放式经营分析",
                "对不确定商品强行落账",
            ],
        },
    ],
    "internal_roles": [
        {"title": "Router / Planner", "body": "判断当前输入是什么任务、是否需要多步执行。"},
        {"title": "Context Builder", "body": "拼出店铺、商品、规则、会话和最近任务上下文。"},
        {"title": "Policy Guard", "body": "判断哪些动作必须确认、哪些动作允许继续。"},
        {"title": "Tool Runner", "body": "真正执行 ASR、识图、OCR、库存查询与库存写入。"},
        {"title": "Reviewer", "body": "在高风险链路里做最后一层质量拦截。"},
        {"title": "Summarizer", "body": "把长任务和长会话压成可恢复摘要。"},
    ],
    "employee_profile_shape": block(
        """
        type EmployeeProfile = {
          employee_id: string
          visible_name: string
          role: string
          visible_to_user: boolean
          persona: {
            tone: string
            style: string
            response_length: "short" | "medium"
          }
          domain_scope: string[]
          skill_ids: string[]
          tool_ids: string[]
          disallowed_actions: string[]
          confirmation_rules: string[]
          handoff_targets: string[]
          memory_scope: "session" | "shop" | "task"
        }
        """
    ),
    "skill_tool_contracts": [
        {
            "title": "员工 = 角色入口",
            "body": "员工负责对外呈现人格与边界，不应该直接等同于模型实例。",
            "items": ["visible_name", "domain_scope", "disallowed_actions", "handoff_targets"],
        },
        {
            "title": "Skill = 业务说明书",
            "body": "Skill 负责告诉 agent 遇到什么情况该怎么判断、怎么解释、什么时候要求补信息。",
            "items": ["库存查询流程", "拍照补盲流程", "确认话术", "低置信处理规则"],
        },
        {
            "title": "Tool / Function = 真正执行器",
            "body": "Function calling 应该绑定封装好的业务函数，而不是让 agent 自己想办法碰数据库。",
            "items": ["query_inventory()", "recognize_product()", "create_confirmation()", "append_inventory_event()"],
        },
    ],
    "agent_mappings": [
        {
            "agent": "小雅",
            "role": "首席调度助理",
            "status": "建议的 runtime mapping",
            "skills": [
                "intent-routing",
                "voice-stock-query-playbook",
                "voice-stock-in-playbook",
                "photo-and-receipt-clarification",
                "confirmation-explanation",
            ],
            "functions": [
                "bootstrap_session()",
                "get_shop_profile()",
                "get_store_rules()",
                "create_task_run()",
                "query_inventory()",
                "recognize_product()",
                "extract_receipt_fields()",
                "create_confirmation()",
                "push_session_update()",
            ],
            "guard": "能解释、能组织流程，但不能直接写库存。",
        },
        {
            "agent": "老李",
            "role": "库存执行岗",
            "status": "建议的 runtime mapping",
            "skills": [
                "inventory-execution",
                "low-stock-suggestion",
                "result-card-generation",
                "confirmed-stock-in",
            ],
            "functions": [
                "query_inventory()",
                "append_inventory_event()",
                "write_audit_log()",
                "create_low_stock_alert()",
                "push_session_update()",
            ],
            "guard": "只能在已确认或低风险前提下执行库存域写入。",
        },
        {
            "agent": "系统 Reviewer",
            "role": "隐形质检角色",
            "status": "高风险链路建议启用",
            "skills": [
                "write-safety-review",
                "low-confidence-review",
                "confirmation-required-check",
            ],
            "functions": [
                "check_policy_rules()",
                "validate_inventory_write()",
                "block_or_escalate()",
            ],
            "guard": "不对外发言，只负责在高风险动作前卡口。",
        },
    ],
    "api_principles": [
        "所有客户端请求统一走 /api/v1。",
        "资源名用复数、kebab-case。",
        "成功响应统一返回 data，失败响应统一返回 error。",
        "写操作尽量返回任务或结果卡，减少客户端二次拼装。",
        "媒体上传和业务消息分离，先上传再提交业务消息。",
    ],
    "error_codes": [
        "media_upload_failed",
        "asr_failed",
        "ocr_failed",
        "recognition_low_confidence",
        "confirmation_required",
        "inventory_conflict",
        "item_not_found",
    ],
    "response_examples": [
        {
            "title": "成功响应",
            "body": block(
                """
                {
                  "data": {}
                }
                """
            ),
        },
        {
            "title": "列表响应",
            "body": block(
                """
                {
                  "data": [],
                  "meta": {
                    "next_cursor": "abc123"
                  }
                }
                """
            ),
        },
        {
            "title": "错误响应",
            "body": block(
                """
                {
                  "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "details": [
                      {
                        "field": "price",
                        "message": "Price is required"
                      }
                    ]
                  }
                }
                """
            ),
        },
    ],
    "ws_endpoint": "WS /api/v1/ws/sessions/:session_id?token=<mock_token>",
    "ws_principles": [
        "REST 负责拉真相，WebSocket 只负责增量回写。",
        "结果卡、确认卡、OCR 卡都作为新消息追加，不做复杂 patch。",
        "聊天页、工作台、账本优先复用同一条 session stream。",
        "一旦 seq 断档或重连成功，前端统一走 REST 补偿同步。",
    ],
    "ws_event_envelope": block(
        """
        {
          "event_id": "evt_01HY9X...",
          "seq": 12,
          "event_type": "task.updated",
          "session_id": "sess_01HY9X...",
          "task_run_id": "task_01HY9X...",
          "message_id": null,
          "occurred_at": "2026-04-03T14:22:31.123Z",
          "data": {}
        }
        """
    ),
    "ws_event_types": [
        {"name": "session.ready", "use": "连接建立后的初始化确认。"},
        {"name": "message.created", "use": "有新消息、结果卡、确认卡或 OCR 卡。"},
        {"name": "task.updated", "use": "TaskRun 状态变化。"},
        {"name": "confirmation.created", "use": "新待确认生成。"},
        {"name": "confirmation.resolved", "use": "确认被通过或拒绝。"},
        {"name": "ocr.updated", "use": "OCR 完成或失败。"},
        {"name": "inventory.updated", "use": "库存事件或纠错事件已写入。"},
        {"name": "alert.updated", "use": "低库存提醒状态变化。"},
        {"name": "stream.keepalive", "use": "保活事件。"},
        {"name": "error", "use": "流程级错误通知。"},
    ],
    "ws_refresh_rules": [
        {
            "screen": "ChatScreen",
            "items": [
                "message.created -> 追加或失效消息流",
                "task.updated -> 更新当前任务状态",
                "confirmation.created -> 刷新待确认列表",
                "confirmation.resolved -> 关闭确认 UI 并刷新消息流",
            ],
        },
        {
            "screen": "DashboardScreen",
            "items": [
                "inventory.updated -> 刷新 summary / low stock",
                "alert.updated -> 刷新低库存提醒",
                "confirmation.created / resolved -> 刷新待确认卡",
            ],
        },
        {
            "screen": "LedgerScreen",
            "items": [
                "inventory.updated -> 刷新库存列表",
                "confirmation.resolved -> 刷新审计时间线",
            ],
        },
    ],
    "ws_reconnect_steps": [
        "首次失败 1s，第二次 2s，第三次 5s，后续最大回退 10s。",
        "连续 3 次失败后提示“实时连接已断开，正在重试”。",
        "重连成功后强制失效消息、待确认、库存和审计相关 query。",
    ],
    "api_groups": [
        {
            "name": "会话与消息",
            "purpose": "为工作群提供统一入口，让语音、图片、单据走相同任务编排链。",
            "items": [
                "POST /api/v1/sessions/bootstrap",
                "GET /api/v1/sessions/:session_id/messages",
                "POST /api/v1/sessions/:session_id/messages",
            ],
        },
        {
            "name": "媒体上传",
            "purpose": "先拿 upload_url，再把 media_id 挂到业务消息上，避免把上传和业务提交混为一层。",
            "items": [
                "POST /api/v1/media-uploads",
            ],
        },
        {
            "name": "库存查询与提醒",
            "purpose": "承接库存搜索、详情查看与低库存提醒，不直接触发写操作。",
            "items": [
                "GET /api/v1/inventory-items?query=红牛",
                "GET /api/v1/inventory-items/:item_id",
                "GET /api/v1/alerts?type=low-stock",
            ],
        },
        {
            "name": "确认链路",
            "purpose": "让高风险和低置信动作统一进入可审计的确认态。",
            "items": [
                "GET /api/v1/confirmations",
                "POST /api/v1/confirmations/:confirmation_id/approve",
                "POST /api/v1/confirmations/:confirmation_id/reject",
            ],
        },
        {
            "name": "OCR 与库存写入",
            "purpose": "OCR 先抽字段，库存写入更常见的路径仍是确认驱动的服务端内部落账。",
            "items": [
                "POST /api/v1/ocr-documents",
                "GET /api/v1/ocr-documents/:ocr_document_id",
                "POST /api/v1/inventory-events",
            ],
        },
    ],
    "data_groups": [
        {
            "name": "会话与任务账本",
            "purpose": "解决当前老板在做什么、任务走到哪一步、正在查还是在等确认。",
            "models": ["ConversationSession", "SessionMessage", "TaskRun", "Confirmation"],
        },
        {
            "name": "库存业务真相",
            "purpose": "承接最终可查询、可纠错、可审计的库存真相。",
            "models": ["InventoryItem", "InventoryEvent", "Alert", "AuditLog"],
        },
        {
            "name": "多模态辅助对象",
            "purpose": "承接媒体引用、OCR 结构化字段与低置信字段列表。",
            "models": ["media_uploads", "OcrDocument"],
        },
    ],
    "consistency_rules": [
        "InventoryItem.current_stock 来自 InventoryEvent 汇总结果。",
        "Correction 不是覆盖，而是追加一条 correction 事件。",
        "Confirmation 一旦通过，必须绑定对应 TaskRun。",
        "OCR 结果不直接写库存，必须先转成确认链。",
        "数据库只存 media_id、URL 和元数据，不存本地磁盘路径真相。",
    ],
    "error_states": [
        {
            "title": "语音失败",
            "body": "这段语音我没听清，您可以再说一遍，或者改成文字。",
        },
        {
            "title": "识图低置信",
            "body": "我大概认出来了，但不敢直接入账，麻烦您确认一下。",
        },
        {
            "title": "OCR 失败",
            "body": "这张单据我没读清，建议重新拍一张更平整的照片。",
        },
        {
            "title": "写库冲突",
            "body": "这条库存刚刚被更新过，我已经帮您刷新到最新结果。",
        },
    ],
    "analytics_events": [
        "voice_entry_tapped",
        "voice_task_submitted",
        "voice_task_completed",
        "voice_query_submitted",
        "photo_stock_in_submitted",
        "photo_query_submitted",
        "receipt_ocr_submitted",
        "confirmation_approved",
        "confirmation_rejected",
        "correction_submitted",
    ],
    "sprint_cards": [
        {
            "name": "Sprint 0",
            "goal": "先把移动端和服务端骨架立起来，让假数据页面能跑。",
            "frontend": [
                "Expo 工程初始化",
                "TypeScript 配置",
                "React Navigation / Query / Zustand 基础搭好",
            ],
            "backend": [
                "API 工程骨架",
                "3 个空页面配套的假数据接口",
            ],
            "acceptance": [
                "能打开工作台、工作群、账本",
                "页面切换顺畅",
                "假数据能渲染",
            ],
        },
        {
            "name": "Sprint 1",
            "goal": "把语音主链路真正跑起来。",
            "frontend": [
                "工作台语音入口",
                "聊天页微信式输入栏",
                "录音采集、上传、语音消息渲染",
            ],
            "backend": [
                "session bootstrap / media upload / send message",
                "基础 ASR 接口编排",
                "语音入库与语音查询 TaskRun",
            ],
            "acceptance": [
                "语音入库能跑通",
                "语音查询能跑通",
                "聊天页能收到结果卡",
            ],
        },
        {
            "name": "Sprint 2",
            "goal": "把拍照和 OCR 加入首版闭环。",
            "frontend": [
                "相机拍照入口",
                "图片预览",
                "+ 工具面板",
                "OCR 结果卡与拍照查询卡",
            ],
            "backend": [
                "商品识别接口",
                "拍照查询接口",
                "OCR 抽取接口",
                "低置信字段标记与待确认生成",
            ],
            "acceptance": [
                "拍照建档进入确认态",
                "拍照查询返回商品与库存",
                "OCR 返回结构化字段",
            ],
        },
        {
            "name": "Sprint 3-4",
            "goal": "把确认、账本、审计和稳定性补齐，让 MVP 能演示、能试点。",
            "frontend": [
                "待确认列表与确认卡编辑",
                "账本列表、审计时间线、人工纠错表单",
                "弱网、上传中、错误文案与微信感细节优化",
            ],
            "backend": [
                "confirmation approve/reject",
                "inventory event / correction event / audit log",
                "低库存提醒、错误码、重试机制、监控日志",
            ],
            "acceptance": [
                "新商品确认后能正式入账",
                "人工纠错能回写账本与聊天",
                "演示时不容易卡死，关键失败路径可理解",
            ],
        },
    ],
    "priority_lanes": [
        {"name": "P0", "items": ["语音入库", "语音查询", "工作群聊天页"]},
        {"name": "P1", "items": ["拍照建档", "拍照查询", "OCR 抽取"]},
        {"name": "P2", "items": ["确认链路", "账本", "审计"]},
        {"name": "P3", "items": ["体验优化", "引导与降级"]},
    ],
    "delivery_roles": [
        {
            "title": "移动端",
            "items": ["React Native 架构", "页面开发", "录音 / 相机 / 上传", "状态管理"],
        },
        {
            "title": "服务端",
            "items": ["REST API", "会话编排", "库存写入与查询", "审计链路"],
        },
        {
            "title": "AI / 多模态",
            "items": ["ASR 接入", "商品识别策略", "OCR 抽取策略", "低置信规则"],
        },
    ],
    "provider_matrix": [
        {"capability": "Auth", "current": "MockAuthProvider", "later": "正式账号体系"},
        {"capability": "Object Storage", "current": "MinIO", "later": "S3 兼容云存储"},
        {"capability": "Router", "current": "RuleFirstRouter", "later": "可选 LLM Router"},
        {"capability": "Summarizer", "current": "TemplateSummarizer", "later": "可选 LLM Summarizer"},
        {"capability": "ASR", "current": "MockAsrProvider", "later": "单一真实 ASR 供应商"},
        {"capability": "OCR", "current": "MockOcrProvider", "later": "单一真实 OCR 供应商"},
        {"capability": "Vision", "current": "MockVisionProvider", "later": "单一真实识图供应商"},
    ],
    "provider_rules": [
        "当前阶段每类能力只保留一个接口，不做多 provider 并行竞争。",
        "mock provider 也必须覆盖 success / low_confidence / failure 三类场景。",
        "进入试点前再选择真实 vendor，前提是主链路和测试基线已经稳定。",
    ],
    "demo_scope": [
        "工作台",
        "微信感工作群",
        "语音入库",
        "语音查询",
        "拍照建档",
        "OCR 结果卡",
        "简化账本",
    ],
    "decision_cards": [
        {
            "title": "D1. 客户端采用 Expo 优先",
            "body": "首版媒体能力和工程效率更重要；如果后续需要深度厂商 SDK，再从 Expo 过渡到 Bare。",
        },
        {
            "title": "D2. 服务端做统一编排",
            "body": "语音、识图、OCR、确认、审计必须在同一规则中心里运行，不能分散到客户端或多个旁路服务。",
        },
        {
            "title": "D3. 语音必须是主入口",
            "body": "这是产品差异化核心，不应该在 MVP 里被拍照或表单方案稀释。",
        },
        {
            "title": "D4. 多模态必须进 MVP",
            "body": "无码商品、货架查询和纸质进货单决定了多模态不是锦上添花，而是基础能力。",
        },
    ],
    "risk_cards": [
        {
            "title": "R1. 语音识别准确率不稳定",
            "impact": "用户会怀疑整个产品的可靠性。",
            "mitigation": "结果卡允许快速修正，失败时给文本兜底，不硬撑错误结论。",
        },
        {
            "title": "R2. 商品冷启动困难",
            "impact": "无码商品最容易把流程卡死。",
            "mitigation": "拍照建档、手工补全、OCR 抽取并行存在，不押注单一识别路径。",
        },
        {
            "title": "R3. OCR 对纸质单据鲁棒性不足",
            "impact": "单据辅助价值会下降，影响首版说服力。",
            "mitigation": "先强调辅助抽字段，不承诺自动入账，把确认链做扎实。",
        },
        {
            "title": "R4. 微信感像了，但流程不像",
            "impact": "用户预期顺手，结果实际操作仍然别扭。",
            "mitigation": "输入方式保持简单，不把企业后台概念硬塞进聊天页。",
        },
    ],
    "open_questions": [
        {
            "title": "Q1. Expo 还是 Bare",
            "body": "当前建议先 Expo，等真的被端侧模型或硬件 SDK 卡住再切。",
        },
        {
            "title": "Q2. 语音识别基座选谁",
            "body": "首版优先最稳，不要一开始就接多个供应商把评估复杂化。",
        },
        {
            "title": "Q3. OCR 与识图供应商怎么选",
            "body": "首版优先准确率与速度，而不是最低成本。",
        },
        {
            "title": "Q4. 首版要不要登录",
            "body": "如果只是演示版可单店单账号；如果准备试点，应尽早加账号与店铺上下文。",
        },
    ],
    "definition_of_done": [
        "能启动 FastAPI、Worker、MySQL、Redis 与 MinIO。",
        "能 bootstrap 出默认工作群 session。",
        "能通过消息接口创建 `TaskRun`。",
        "`voice-stock-in` 能走到确认态并确认后写入库存事件。",
        "`voice-stock-query` 能返回只读结果卡。",
        "聊天页能通过 WebSocket 收到任务状态和结果回写。",
        "所有 AI 能力都通过 provider interface，而不是散落在业务代码里。",
    ],
    "workspace_status": [
        {
            "title": "文档蓝图",
            "status": "已成施工包",
            "body": "00-13 已经把技术栈、架构、API、数据、AI 系统、实时合同、DB schema 和 provider 策略补到可施工层。",
        },
        {
            "title": "showcase 页面",
            "status": "可俯瞰审视",
            "body": "现在它不仅做总控台，还同步了当前施工范围、runtime 合同、实时事件、DB 施工约定和 provider 策略。",
        },
        {
            "title": "React Native 客户端",
            "status": "待实现",
            "body": "当前工作区还没有真正的移动端工程，只定义了目录蓝图、状态边界和交互原则。",
        },
        {
            "title": "业务后端",
            "status": "待实现",
            "body": "当前也没有真正的 FastAPI 业务服务、MySQL 模型和 Celery 编排，只存在介绍站。",
        },
        {
            "title": "员工 agent runtime",
            "status": "待实现",
            "body": "EmployeeProfile、skill_ids、tool_ids 和 function calling 映射现在仍停留在设计层。",
        },
        {
            "title": "Function calling",
            "status": "建议已清晰",
            "body": "正确方向已经明确：skill 是规则说明，tool/function 是封装好的业务函数，由 agent 受控调用。",
        },
    ],
    "review_checklist": [
        "用户是否一眼看出这是语音优先，而不是另一个复杂库存 App？",
        "工作群是否真的像微信，而不是披着聊天皮的后台表单？",
        "多模态是否只是展示能力，还是确实补齐了语音的信息缺口？",
        "确认链是否既足够安全，又不至于把高频操作做得很繁琐？",
        "账本是否能让用户真心相信系统的写入结果是可查、可改、可追溯的？",
        "服务端是否已经被设计成控制平面，而不是一堆零散接口？",
        "AI 员工是否有明确边界，而不是多开几个会说话的模型？",
        "当前原型和未来要做的系统之间，哪些已经成型，哪些还是蓝图？",
    ],
    "docs_index": [
        {
            "path": "project_docs/00-final-tech-stack.md",
            "summary": "最终技术栈、异步与实时策略、对象存储与部署方式。",
            "answers": "这个项目到底用什么栈，为什么这样定。",
        },
        {
            "path": "project_docs/01-react-native-architecture.md",
            "summary": "客户端架构、目录建议、导航形态、前后端职责边界。",
            "answers": "React Native 工程怎么搭，页面和模块怎么切。",
        },
        {
            "path": "project_docs/02-api-contract.md",
            "summary": "REST API 资源、会话消息、媒体上传、确认链路与 OCR 合同。",
            "answers": "客户端和服务端到底按什么接口说话。",
        },
        {
            "path": "project_docs/03-data-models.md",
            "summary": "Session、TaskRun、InventoryEvent、Confirmation、AuditLog 等统一对象。",
            "answers": "系统里哪些对象是真正的结构化真相。",
        },
        {
            "path": "project_docs/04-client-state-and-flows.md",
            "summary": "三主页面、关键 UI 状态、六条主流程状态机和错误态。",
            "answers": "页面与状态到底怎么跑，错误怎么回。",
        },
        {
            "path": "project_docs/05-sprint-plan.md",
            "summary": "Sprint 0 到 Sprint 4 的交付拆解、优先级与 Demo 最小集合。",
            "answers": "这个项目应该怎么按阶段推进。",
        },
        {
            "path": "project_docs/06-risks-and-decisions.md",
            "summary": "默认决策、最大风险、缓解策略和待拍板问题。",
            "answers": "首版最大的不确定性和关键取舍是什么。",
        },
        {
            "path": "project_docs/07-ai-employee-and-ai-native-system.md",
            "summary": "AI 员工角色合同、四层结构、控制平面思路与产品化建议。",
            "answers": "AI 员工怎么设计，系统怎样真正 AI 原生。",
        },
        {
            "path": "project_docs/08-claw-code-applicability-assessment.md",
            "summary": "Claw Code 可借与不可借之处，以及如何转译成业务 agent runtime。",
            "answers": "该借什么框架思想，哪些不能直接搬。",
        },
        {
            "path": "project_docs/09-implementation-scope.md",
            "summary": "当前施工目标、纳入范围、明确不做项、推荐仓库结构和完成定义。",
            "answers": "这轮正式施工到底做什么、不做什么，以及做到什么算第一阶段完成。",
        },
        {
            "path": "project_docs/10-runtime-contracts.md",
            "summary": "EmployeeProfile、ToolSpec、PolicyRule、TaskRun 迁移和 handoff 约束。",
            "answers": "runtime 到底如何按合同实现，而不是停留在 agent 理念层。",
        },
        {
            "path": "project_docs/11-realtime-contract.md",
            "summary": "WebSocket 入口、事件包结构、事件类型、前端失效刷新和重连补偿。",
            "answers": "聊天、确认、OCR、库存更新到底通过什么实时协议回写。",
        },
        {
            "path": "project_docs/12-db-schema.md",
            "summary": "MySQL 施工级表结构、索引、字段精度、迁移顺序和物理约束。",
            "answers": "Alembic 和 SQLAlchemy 该按什么 schema 真正开工。",
        },
        {
            "path": "project_docs/13-provider-decisions.md",
            "summary": "mock-first provider 策略、接口边界、切换真实供应商的时机和约束。",
            "answers": "这轮 provider 怎么定，什么时候再切真实 ASR / OCR / 识图能力。",
        },
    ],
}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, **SHOWCASE_DATA})


@app.get("/api/overview")
async def overview():
    return {
        "project": "AI数字店铺大管家",
        "mode": "god-view-prototype-console",
        "implementation_mode": "real-backbone-with-mock-ai-providers",
        "frontend": "React Native + Expo",
        "backend": "FastAPI + MySQL + Celery + Redis + WebSocket",
        "provider_strategy": "mock-first",
        "realtime_transport": "session-scoped WebSocket",
        "visible_agents": ["小雅", "老李"],
        "core_flows": [
            "语音入库",
            "语音查询",
            "拍照建档",
            "拍照查询",
            "进货单 OCR",
            "人工纠错",
        ],
        "internal_roles": [
            "Router / Planner",
            "Context Builder",
            "Policy Guard",
            "Tool Runner",
            "Reviewer",
            "Summarizer",
        ],
        "docs_covered": len(SHOWCASE_DATA["docs_index"]),
        "workspace_status": [
            item["status"] for item in SHOWCASE_DATA["workspace_status"]
        ],
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
