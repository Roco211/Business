"""
Volcano Engine (火山引擎) LLM integration for the AI Store Manager.
Uses OpenAI-compatible API for intent classification, entity extraction,
and conversational responses.
"""
import json
import os
from openai import OpenAI

VOLCENGINE_API_KEY = os.getenv("VOLCENGINE_API_KEY", "5dda09ff-2b12-49d9-9528-c19fb769e483")
VOLCENGINE_BASE_URL = os.getenv("VOLCENGINE_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
VOLCENGINE_MODEL = os.getenv("VOLCENGINE_MODEL", "doubao-1-5-pro-32k-250115")

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=VOLCENGINE_API_KEY,
            base_url=VOLCENGINE_BASE_URL,
        )
    return _client


def _chat(system: str, user: str, *, temperature: float = 0.1, json_mode: bool = False) -> str:
    """Call Volcano Engine chat completion. Returns content string."""
    content, _ = _chat_with_usage(system, user, temperature=temperature, json_mode=json_mode)
    return content


def _chat_with_usage(system: str, user: str, *, temperature: float = 0.1, json_mode: bool = False):
    """Call Volcano Engine chat completion. Returns (content, usage_dict)."""
    import time
    client = _get_client()
    kwargs = {
        "model": VOLCENGINE_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": 2048,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    t0 = time.time()
    resp = client.chat.completions.create(**kwargs)
    latency_ms = int((time.time() - t0) * 1000)
    content = resp.choices[0].message.content.strip()
    usage = {
        "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0) if resp.usage else 0,
        "completion_tokens": getattr(resp.usage, "completion_tokens", 0) if resp.usage else 0,
        "total_tokens": getattr(resp.usage, "total_tokens", 0) if resp.usage else 0,
        "latency_ms": latency_ms,
        "model": VOLCENGINE_MODEL,
    }
    return content, usage


# ── Intent Classification ──────────────────────────────────────────────

INTENT_CLASSIFY_SYSTEM = """你是一个五金店AI助手的意图分类器。
根据用户的消息，判断用户意图并以JSON格式返回。

可选意图：
- "stock_in"：用户要进货/入库（如"进了10盒螺丝"、"今天到货5箱砂纸"）
- "stock_out"：用户要出库/销售（如"卖出2个开关"、"给客户拿3卷生料带"）
- "stock_query"：用户查询库存（如"螺丝还有多少"、"哪些货快没了"）
- "item_create"：用户要添加新商品（如"加一个新商品：锤子"）
- "correction"：用户要修正库存（如"螺丝数量不对，应该是30"）
- "list_items"：用户要查看商品列表（如"都有哪些货"、"列一下库存"）
- "low_stock"：用户要查看低库存预警（如"哪些快卖完了"）
- "general_chat"：普通对话/打招呼/其他

返回格式（严格JSON）：
{
    "intent": "意图类型",
    "confidence": 0.0-1.0,
    "reasoning": "简短理由"
}"""


def _keyword_classify(user_message: str) -> str:
    """Fallback keyword-based intent classification."""
    msg = user_message.lower()
    # Stock out
    if any(w in msg for w in ["卖出", "出库", "卖掉", "给客户", "拿走", "出售"]):
        return "stock_out"
    # Stock query
    if any(w in msg for w in ["多少", "还有", "查询", "查一下", "剩", "库存", "有没有"]):
        return "stock_query"
    # Low stock
    if any(w in msg for w in ["快没了", "快卖完", "低库存", "预警", "补货", "哪些货"]):
        return "low_stock"
    # List items
    if any(w in msg for w in ["列出", "所有商品", "全部", "清单", "看看都有"]):
        return "list_items"
    # Item create
    if any(w in msg for w in ["新商品", "添加", "加一个", "新增", "创建"]):
        return "item_create"
    # Correction
    if any(w in msg for w in ["修正", "纠正", "不对", "应该是", "改成"]):
        return "correction"
    # Stock in
    if any(w in msg for w in ["进", "入库", "进了", "到货", "进了", "补货"]):
        return "stock_in"
    # Greeting
    if any(w in msg for w in ["你好", "嗨", "hi", "hello", "早上好", "晚上好"]):
        return "general_chat"
    return "general_chat"


def classify_intent(user_message: str) -> dict:
    """Classify user message intent using LLM with fallback."""
    try:
        raw = _chat(INTENT_CLASSIFY_SYSTEM, user_message, json_mode=True)
        result = json.loads(raw)
        return {
            "intent": result.get("intent", "general_chat"),
            "confidence": float(result.get("confidence", 0.5)),
            "reasoning": result.get("reasoning", ""),
        }
    except Exception:
        return {
            "intent": _keyword_classify(user_message),
            "confidence": 0.6,
            "reasoning": "关键词匹配(离线模式)",
        }


# ── Entity Extraction ──────────────────────────────────────────────────

EXTRACT_SYSTEM = """你是五金店的实体提取器。从用户消息中提取结构化信息。
返回严格的JSON格式。

对于入库/出库操作，提取：
{
    "items": [
        {
            "name": "商品名称",
            "quantity": 数量(数字),
            "unit": "单位（件/盒/卷/米/个/把/张/支/包/箱）",
            "price": 单价(数字,可为null)
        }
    ],
    "note": "备注"
}

对于查询操作，提取：
{
    "item_name": "要查询的商品名",
    "query_type": "specific/low_stock/all"
}

对于修正操作，提取：
{
    "item_name": "商品名称",
    "target_stock": 目标数量,
    "reason": "修正原因"
}

对于添加商品，提取：
{
    "name": "商品名称",
    "category": "分类",
    "unit": "默认单位",
    "initial_stock": 初始库存,
    "price": 单价
}"""


import re


def _extract_entities_regex(user_message: str, intent: str) -> dict:
    """Fallback regex-based entity extraction."""
    msg = user_message

    if intent in ("stock_in", "stock_out"):
        # Try to extract: 进了20盒螺丝钉, 卖出3卷生料带
        patterns = [
            r'(?:进了?|进货|卖出|出库|卖掉)\s*(\d+(?:\.\d+)?)\s*(盒|卷|米|个|把|张|支|包|箱|件)\s*(.+)',
            r'(\d+(?:\.\d+)?)\s*(盒|卷|米|个|把|张|支|包|箱|件)\s*(.+?)(?:入库|出库|进货|卖出)',
        ]
        for p in patterns:
            m = re.search(p, msg)
            if m:
                return {
                    "items": [{
                        "name": m.group(3).strip(),
                        "quantity": float(m.group(1)),
                        "unit": m.group(2),
                        "price": None
                    }]
                }
        # Try simpler: 进了20个锤子
        m = re.search(r'(\d+(?:\.\d+)?)\s*(?:个|件|盒|卷|把|张|支|包|箱|米)?\s*(.+)', msg)
        if m:
            return {"items": [{"name": m.group(2).strip(), "quantity": float(m.group(1)), "unit": "件", "price": None}]}

    if intent == "stock_query":
        for name in ["螺丝钉", "螺母", "铁丝", "砂纸", "生料带", "电线", "开关", "水管接头", "万能胶", "油漆刷"]:
            if name in msg:
                return {"item_name": name, "query_type": "specific"}
        if any(w in msg for w in ["所有", "全部", "哪些"]):
            return {"query_type": "all"}
        return {"query_type": "all"}

    if intent == "correction":
        m = re.search(r'(.+?)(?:应该?是|改成|改为|修正为?)\s*(\d+(?:\.\d+)?)', msg)
        if m:
            return {"item_name": m.group(1).strip(), "target_stock": float(m.group(2)), "reason": "AI修正"}

    if intent == "item_create":
        m = re.search(r'(?:加|新增|创建|添加)\s*(?:一个?)?\s*(?:新商品[：:]\s*)?(.+)', msg)
        if m:
            return {"name": m.group(1).strip(), "category": "", "unit": "件", "initial_stock": 0, "price": 0}

    return {}


def extract_entities(user_message: str, intent: str) -> dict:
    """Extract structured entities from user message based on intent."""
    try:
        prompt = f"用户意图：{intent}\n用户消息：{user_message}\n请提取结构化信息。"
        raw = _chat(EXTRACT_SYSTEM, prompt, json_mode=True)
        return json.loads(raw)
    except Exception:
        return _extract_entities_regex(user_message, intent)


# ── Response Generation ────────────────────────────────────────────────

RESPONSE_SYSTEM = """你是"小雅"，一个五金店的AI数字店员。你用简洁、自然的中文回复老板的指令。

回复风格：
- 称呼用户为"老板"
- 语气专业但亲切，像一个靠谱的老员工
- 回复简洁明了，不啰嗦
- 遇到不确定的事情会确认
- 主动提醒低库存商品
- 操作完成后可以适当给建议（如"这批货放货架B区比较合适"）

回复内容要根据操作结果生成，包括：
- 入库：确认数量，可以建议摆放位置
- 出库：确认数量，提醒库存变化
- 查询：列出关键数据，低库存要警告
- 添加商品：确认添加成功
- 修正：确认修正前后数值

你会根据系统提供的操作结果，生成自然语言回复给老板。"""


def _generate_fallback_response(user_message: str, action_result: dict) -> str:
    """Generate a response when LLM is unavailable."""
    if not action_result.get("success", True):
        return f"老板，操作遇到了问题：{action_result.get('error', '未知错误')}。请检查一下。"

    action = action_result.get("action", "")
    items = action_result.get("items", [])

    if action == "入库":
        if items:
            names = "、".join(f"{i['name']}{i['quantity']}{i['unit']}" for i in items if 'name' in i)
            return f"好的老板！已经完成入库：{names}。库存已更新，随时可以查询。"
        return "老板，入库完成！"

    if action == "出库":
        results = []
        for i in items:
            if 'error' in i:
                results.append(f"{i['name']}：{i['error']}")
            else:
                results.append(f"{i['name']}出库{i['quantity']}，剩余{i['remaining']}")
        return "老板，出库结果：\n" + "\n".join(results)

    if action == "查询":
        if not items:
            return "老板，没有找到相关商品。"
        lines = []
        for i in items:
            status = "⚠️ 库存偏低" if i.get('low') else "✅ 正常"
            lines.append(f"• {i['name']}：{i['stock']} {i['unit']} {status}")
        return "老板，查询结果：\n" + "\n".join(lines)

    if action == "添加商品":
        item = action_result.get("item", {})
        return f"好的老板！已添加新商品：{item.get('name', '未知')}。可以在库存列表中看到了。"

    if action == "修正":
        return f"老板，{action_result.get('item', '')}的库存已从{action_result.get('old_stock', 0)}修正为{action_result.get('new_stock', 0)}。"

    if action == "列表":
        if not items:
            return "老板，库存里暂时没有商品。"
        lines = [f"• {i['name']}（{i['category'] or '未分类'}）：{i['stock']} {i['unit']}，单价¥{i['price']}" for i in items]
        return f"老板，当前库存共{len(items)}种商品：\n" + "\n".join(lines)

    if action == "低库存预警":
        if not items:
            return "老板，目前所有商品库存都充足！👍"
        lines = [f"• {i['name']}：仅剩{i['stock']} {i['unit']}（阈值{i['threshold']}）" for i in items]
        return f"老板，以下商品库存偏低，建议补货：\n" + "\n".join(lines)

    return f"老板，操作已完成！"


def generate_response(user_message: str, action_result: dict) -> str:
    """Generate natural language response based on action result."""
    try:
        prompt = f"""老板说：{user_message}

操作结果：
{json.dumps(action_result, ensure_ascii=False, indent=2)}

请根据操作结果生成一个简洁的回复给老板。如果是查询结果，列出关键信息。
如果是操作成功，确认完成。如果有错误，说明原因。"""
        return _chat(RESPONSE_SYSTEM, prompt, temperature=0.7)
    except Exception:
        return _generate_fallback_response(user_message, action_result)


# ── Conversational Chat ────────────────────────────────────────────────

CHAT_SYSTEM = """你是"小雅"，一家五金店的AI数字店员。你经验丰富，熟悉各种五金产品。

你的专业知识：
- 紧固件：螺丝、螺母、螺栓、垫圈、铆钉等
- 水暖配件：水管、接头、阀门、生料带、水龙头等
- 电气材料：电线、开关、插座、灯具、配电箱等
- 工具：扳手、钳子、螺丝刀、锤子、电钻等
- 涂料：油漆、涂料、刷子、滚筒、砂纸等
- 粘合剂：胶水、AB胶、玻璃胶、免钉胶等
- 其他：铁丝、铁钉、膨胀螺丝、扎带等

你的特点：
- 称呼用户为"老板"
- 主动提供建议和提醒
- 如果用户询问产品用途，给出具体建议
- 注意安全事项（如电气操作要断电）
- 提醒低库存商品

用简洁专业的中文回复。"""


def chat_stream(user_message: str, history: list[dict] | None = None):
    """Yield tokens as a generator for streaming responses."""
    try:
        client = _get_client()
        messages = [{"role": "system", "content": CHAT_SYSTEM}]
        if history:
            messages.extend(history[-10:])
        messages.append({"role": "user", "content": user_message})
        stream = client.chat.completions.create(
            model=VOLCENGINE_MODEL,
            messages=messages,
            temperature=0.8,
            max_tokens=1024,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        import traceback
        print(f"[LLM Stream Error] {type(e).__name__}: {e}")
        # Fallback: yield full response at once
        yield _chat_fallback_reply(user_message)


def _chat_fallback_reply(user_message: str) -> str:
    """Fallback replies when LLM is unavailable."""
    msg = user_message.lower()
    if any(w in msg for w in ["你好", "嗨", "hi", "hello"]):
        return "老板你好！我是小雅，你的AI数字店员。有什么可以帮你的吗？你可以告诉我进货、出库、查询库存等操作。"
    if any(w in msg for w in ["谢谢", "感谢"]):
        return "不客气老板！有什么需要随时吩咐。"
    if any(w in msg for w in ["帮助", "怎么用", "功能"]):
        return """老板，我可以帮你：
• 进货入库（如"进了20盒螺丝钉"）
• 出库销售（如"卖出3卷生料带"）
• 查询库存（如"铁丝还有多少"）
• 添加新商品（如"加一个锤子"）
• 修正库存（如"砂纸应该是50张"）
• 查看低库存预警

你直接告诉我就行！"""
    return '老板，我理解你说的。不过我现在主要帮你管理库存，你可以试试说"进了10盒螺丝钉"这样的指令。'


def chat_reply(user_message: str, history: list[dict] | None = None) -> str:
    """General conversational reply."""
    reply, _ = chat_reply_with_usage(user_message, history)
    return reply


def chat_reply_with_usage(user_message: str, history: list[dict] | None = None):
    """General conversational reply with token usage tracking."""
    import time
    try:
        client = _get_client()
        messages = [{"role": "system", "content": CHAT_SYSTEM}]
        if history:
            messages.extend(history[-10:])  # Keep last 10 messages for context
        messages.append({"role": "user", "content": user_message})
        t0 = time.time()
        resp = client.chat.completions.create(
            model=VOLCENGINE_MODEL,
            messages=messages,
            temperature=0.8,
            max_tokens=1024,
        )
        latency_ms = int((time.time() - t0) * 1000)
        reply = resp.choices[0].message.content.strip()
        usage = {
            "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0) if resp.usage else 0,
            "completion_tokens": getattr(resp.usage, "completion_tokens", 0) if resp.usage else 0,
            "total_tokens": getattr(resp.usage, "total_tokens", 0) if resp.usage else 0,
            "latency_ms": latency_ms,
            "model": VOLCENGINE_MODEL,
        }
        return reply, usage
    except Exception as e:
        import traceback
        print(f"[LLM Error] {type(e).__name__}: {e}")
        traceback.print_exc()
        return _chat_fallback_reply(user_message)
