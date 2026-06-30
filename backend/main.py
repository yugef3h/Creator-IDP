"""ChatBI V1.0 — FastAPI + SSE 流式后端。

启动：python3 -m uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime
from typing import AsyncGenerator

from dotenv import load_dotenv

load_dotenv()

# 确保根目录在 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from models import SchemaElement, SemanticParseInfo
from trie_index import build_index, match
from rule_parser import parse as rule_parse
from translator import translate
from executor import execute as exec_sql

from backend.context import load_context, save_context, rewrite_multi_turn
from backend.correctors import correct
from backend.processors.data_interpret import interpret
from backend.processors.metric_ratio import calc_ratio
from backend.processors.dimension_recommend import recommend as recommend_dimensions

# ============================================================
# 初始化
# ============================================================
app = FastAPI(title="ChatBI V1.0", version="1.0.0")

# CORS
with open("backend/config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)
origins = config["server"]["cors_origins"]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

# 加载 schema + 构建索引
with open("dataset.yaml", "r", encoding="utf-8") as f:
    raw = yaml.safe_load(f)

ELEMENTS: list[SchemaElement] = []
ds = raw["datasets"][0]
for m in ds.get("metrics", []):
    ELEMENTS.append(SchemaElement(
        id=m["id"], biz_name=m["biz_name"], name=m.get("name"),
        alias=m.get("alias", ""), description=m.get("description", ""),
        data_type=m.get("data_type", "NUMERIC"),
        default_agg=m.get("default_agg", ""),
        expression=m.get("expression"), table=m.get("table"),
        element_type="METRIC",
    ))
for d in ds.get("dimensions", []):
    ELEMENTS.append(SchemaElement(
        id=d["id"], biz_name=d["biz_name"], name=d.get("name"),
        alias=d.get("alias", ""), description=d.get("description", ""),
        data_type=d.get("data_type", "CATEGORY"),
        default_agg="",
        join_table=d.get("join_table"), join_key=d.get("join_key"),
        table=d.get("table"),
        element_type="DIMENSION",
    ))

INDEX = build_index(ELEMENTS)
TRIE_KEYS = set(INDEX.keys())

print(f"[ChatBI] Schema loaded: {len(ELEMENTS)} elements, {len(TRIE_KEYS)} trie keys")


# ============================================================
# SSE 辅助
# ============================================================
def sse_event(event_type: str, data: dict | None = None, text: str | None = None) -> str:
    """构建 SSE 事件字符串。"""
    payload = {}
    if data is not None:
        payload = {"type": event_type, "data": data}
    else:
        payload = {"type": event_type}
    if text is not None:
        payload["text"] = text
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# ============================================================
# 核心 API
# ============================================================
@app.post("/api/chat/query")
async def chat_query(request: Request):
    """核心查询端点：SSE 流式返回。"""
    body = await request.json()
    query_text = body.get("queryText", "").strip()
    chat_id = body.get("chatId", str(uuid.uuid4())[:8])
    date_range = body.get("dateRange")  # {start: "2026-06-23", end: "2026-06-30"} 可选

    if not query_text:
        return StreamingResponse(
            iter([sse_event("error", data={"message": "查询不能为空"})]),
            media_type="text/event-stream",
        )

    async def generate() -> AsyncGenerator[str, None]:
        # --- Layer 2: 多轮改写 ---
        history = load_context(chat_id)
        current_query = query_text
        if history:
            current_query = rewrite_multi_turn(query_text, history)

        # --- Layer 3: RAG（Trie 匹配） ---
        matched = match(current_query, INDEX)

        # --- Layer 1: Parse ---
        parse_info = rule_parse(current_query, matched, TRIE_KEYS)
        if parse_info is None or not parse_info.s2sql:
            yield sse_event("error", data={
                "message": "抱歉，我无法理解这个问题。",
                "suggestion": "试试：最近7天播放量趋势、各分区播放量排名",
            })
            return

        # 用户手动指定日期范围 → 覆盖自动提取的
        if date_range and date_range.get("start") and date_range.get("end"):
            parse_info.date_info = {"start": date_range["start"], "end": date_range["end"]}

        # 发送 parse_info
        yield sse_event("parse_info", data={
            "metrics": [m.biz_name for m in parse_info.metrics],
            "dimensions": [d.biz_name for d in parse_info.dimensions],
            "dateInfo": parse_info.date_info,
            "queryMode": parse_info.query_mode,
        })

        # --- Correct ---
        parse_info = correct(parse_info, ELEMENTS)

        # --- Translate ---
        try:
            physical_sql = translate(parse_info.s2sql)
            parse_info.query_sql = physical_sql
        except Exception as e:
            yield sse_event("error", data={"message": f"SQL翻译失败: {e}"})
            return

        # --- Execute ---
        try:
            result = exec_sql(physical_sql)
            result.parse_info = parse_info
        except Exception as e:
            yield sse_event("error", data={"message": f"查询执行失败: {e}"})
            return

        # 发送 query_result
        yield sse_event("query_result", data={
            "columns": [{"name": c.name, "showType": c.show_type} for c in result.columns],
            "rows": [list(row) for row in result.rows],
            "sql": physical_sql,
        })

        # --- Layer 5: LLM 解读（流式） ---
        if parse_info.query_mode in ("METRIC_GROUPBY", "METRIC_TREND", "METRIC_ORDERBY"):
            async for chunk in interpret(current_query, result):
                yield sse_event("summary_chunk", text=chunk)

        # --- Layer 2: 保存上下文 ---
        save_context(chat_id, current_query, parse_info)

        # --- Layer 5: 归因分析 ---
        ratio_data = calc_ratio(parse_info)
        drill_dims = recommend_dimensions(parse_info.metrics, parse_info.dimensions)

        # 完成
        yield sse_event("done", data={
            "chatId": chat_id,
            "ratio": ratio_data,                          # 环比/同比
            "recommendedDimensions": drill_dims,          # 下钻推荐
            "dateInfo": parse_info.date_info,              # 当前周期
        })

    return StreamingResponse(generate(), media_type="text/event-stream")


# ============================================================
# 辅助端点
# ============================================================
@app.get("/api/chat/history/{chat_id}")
async def get_history(chat_id: str):
    """加载历史对话。"""
    ctx = load_context(chat_id)
    if ctx:
        return {"chatId": chat_id, "history": ctx}
    return {"chatId": chat_id, "history": None}


@app.delete("/api/chat/history/{chat_id}")
async def delete_history(chat_id: str):
    """清除上下文。"""
    import sqlite3
    conn = sqlite3.connect("bilibili_demo.db")
    conn.execute("DELETE FROM chat_context WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()
    return {"status": "ok"}


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "1.0.0", "timestamp": datetime.now().isoformat()}
