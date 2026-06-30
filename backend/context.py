"""多轮对话：上下文持久化 + LLM 改写。"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime

from models import SemanticParseInfo


def _ensure_table():
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
    _ensure_table()
    conn = sqlite3.connect("bilibili_demo.db")
    conn.execute(
        "INSERT OR REPLACE INTO chat_context (chat_id, query_text, parse_info, updated_at) VALUES (?, ?, ?, ?)",
        (chat_id, query_text, json.dumps(_serialize(parse_info), ensure_ascii=False),
         datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def load_context(chat_id: str) -> dict | None:
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
    """用 LLM 融合历史上下文和当前追问，输出独立完整的问题。"""
    hist_query = history.get("query_text", "")
    hist_parse = history.get("parse_info", {})

    # 如果历史没有实质内容，直接返回
    if not hist_query or not hist_parse.get("metrics"):
        return current_query

    # 当前查询已经完整（含指标关键词），不需要改写
    hist_metrics = [m for m in hist_parse.get("metrics", [])]
    if any(m in current_query for m in hist_metrics):
        return current_query

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        # 无 LLM 时做简单拼接
        return f"{hist_query} {current_query}"

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=api_key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )

        prompt = f"""#Role: 数据分析需求分析师
#Task: 将用户的追问融合历史上下文，改写为独立完整的数据查询问题。

#Rules:
1. 保留历史中的指标、维度、日期范围
2. 融入当前追问中的新约束（新维度、过滤条件等）
3. 只输出改写后的问题，不要解释

#History: {hist_query}
#History SQL: {hist_parse.get('query_sql', '')}

#Current: {current_query}

#Rewritten:"""

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=100,
        )
        rewritten = response.choices[0].message.content.strip()
        print(f"  [MultiTurn] '{current_query}' → '{rewritten}'")
        return rewritten
    except Exception as e:
        print(f"  [MultiTurn] LLM rewrite failed: {e}")
        return f"{hist_query} {current_query}"


def _serialize(p: SemanticParseInfo) -> dict:
    return {
        "metrics": [m.biz_name for m in p.metrics],
        "dimensions": [d.biz_name for d in p.dimensions],
        "filters": p.filters,
        "date_info": p.date_info,
        "s2sql": p.s2sql,
        "query_sql": p.query_sql,
        "query_mode": p.query_mode,
    }
