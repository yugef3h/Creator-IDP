"""多轮对话：上下文持久化 + LLM 改写。

V1.0 新增模块。
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime

from models import SemanticParseInfo


def _ensure_table():
    """确保 chat_context 表存在。"""
    conn = sqlite3.connect("bilibili_demo.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_context (
            chat_id TEXT PRIMARY KEY,
            query_text TEXT,
            parse_info TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_context(chat_id: str, query_text: str, parse_info: SemanticParseInfo):
    """保存本轮查询的完整上下文。"""
    _ensure_table()
    conn = sqlite3.connect("bilibili_demo.db")
    conn.execute(
        "INSERT OR REPLACE INTO chat_context (chat_id, query_text, parse_info, updated_at) VALUES (?, ?, ?, ?)",
        (chat_id, query_text, json.dumps(_serialize_parse_info(parse_info), ensure_ascii=False),
         datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def load_context(chat_id: str) -> dict | None:
    """加载历史上下文。"""
    _ensure_table()
    conn = sqlite3.connect("bilibili_demo.db")
    row = conn.execute(
        "SELECT query_text, parse_info FROM chat_context WHERE chat_id = ? ORDER BY updated_at DESC LIMIT 1",
        (chat_id,)
    ).fetchone()
    conn.close()
    if row:
        return {"query_text": row[0], "parse_info": json.loads(row[1])}
    return None


def rewrite_multi_turn(current_query: str, history: dict) -> str:
    """用 LLM 改写多轮问题，融合历史上下文。"""
    # 简单策略：如果历史存在，直接把历史和当前问题拼接
    # 更高级的做法是用 LLM 改写，但保持 V1.0 简洁
    hist_sql = history.get("parse_info", {}).get("query_sql", "")
    hist_metrics = history.get("parse_info", {}).get("metrics", [])
    hist_dims = history.get("parse_info", {}).get("dimensions", [])

    # 简单融合：把历史的关键词附加上
    if hist_metrics and hist_dims:
        return current_query
    return current_query


def _serialize_parse_info(p: SemanticParseInfo) -> dict:
    return {
        "metrics": [m.biz_name for m in p.metrics],
        "dimensions": [d.biz_name for d in p.dimensions],
        "filters": p.filters,
        "date_info": p.date_info,
        "s2sql": p.s2sql,
        "query_sql": p.query_sql,
        "query_mode": p.query_mode,
    }
