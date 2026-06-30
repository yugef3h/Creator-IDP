"""LLM 解析器：DeepSeek prompt + few-shot → S2SQL，规则解析的兜底方案。"""

from __future__ import annotations

import json
import os
import yaml
from datetime import datetime

from openai import OpenAI
from models import SchemaElement, SemanticParseInfo


def _load_exemplars() -> list[dict]:
    with open("exemplars.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _load_schema() -> dict:
    with open("dataset.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _format_schema_string() -> str:
    """格式化为紧凑的 schema 字符串，注入 LLM prompt。"""
    schema = _load_schema()
    ds = schema["datasets"][0]

    metric_lines = []
    for m in ds["metrics"]:
        expr = f" EXPR '{m['expression']}'" if m.get("expression") else ""
        metric_lines.append(
            f"  <{m['biz_name']} ALIAS '{m.get('alias', '')}' "
            f"COMMENT '{m.get('description', '')}' AGGREGATE '{m.get('default_agg', '')}'{expr}>"
        )

    dim_lines = []
    for d in ds["dimensions"]:
        dim_lines.append(
            f"  <{d['biz_name']} ALIAS '{d.get('alias', '')}' "
            f"DATATYPE '{d.get('data_type', '')}'>"
        )

    return (
        f"Table=[video_stats]\n"
        f"Metrics=[\n" + "\n".join(metric_lines) + "\n]\n"
        f"Dimensions=[\n" + "\n".join(dim_lines) + "\n]"
    )


def _select_exemplars(query: str, top_k: int = 3) -> str:
    """从 exemplars 中选最相关的 few-shot。简化版：随机选 + 固定关键示例。"""
    exemplars = _load_exemplars()
    # 简单策略：取前几条 + 关键词匹配
    selected = exemplars[:top_k]
    return "\n".join(
        f"Q: {ex['question']}\nSQL: {ex['s2sql']}"
        for ex in selected
    )


def parse(query: str, matched_elements: list[SchemaElement]) -> SemanticParseInfo | None:
    """LLM 兜底解析。用 DeepSeek 生成 S2SQL。"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return None

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )

    schema_str = _format_schema_string()
    exemplars_str = _select_exemplars(query)

    prompt = f"""#Role: You are a data analyst experienced in SQL languages.
#Task: Convert natural language to SQL query using ONLY the schema elements provided.

#Rules:
1. Use ONLY metrics and dimensions listed in the Schema section below
2. Reference columns by their exact bizName shown in Schema (e.g. "views", "category")
3. ALWAYS apply an aggregate function (SUM/COUNT/AVG) to metric columns unless user asks for raw detail
4. Put date filters in WHERE clause using stat_date
5. DO NOT invent table names or column names — only use what's in the Schema
6. If the question cannot be answered, output CANNOT_PARSE
7. Output ONLY the SQL, no explanation

#Exemplars:
{exemplars_str}

#Query:
Question: {query}
Schema: {schema_str}
SideInfo: CurrentDate={datetime.now().strftime('%Y-%m-%d')}

#SQL:"""

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=500,
        )
        s2sql = response.choices[0].message.content.strip()

        # 清理 markdown 代码块
        if s2sql.startswith("```"):
            s2sql = s2sql.strip("`").strip()
            if s2sql.lower().startswith("sql"):
                s2sql = s2sql[3:].strip()

        if "CANNOT_PARSE" in s2sql.upper():
            return None

        metrics = [e for e in matched_elements if e.element_type == "METRIC"]
        dimensions = [e for e in matched_elements if e.element_type == "DIMENSION"]

        return SemanticParseInfo(
            metrics=metrics,
            dimensions=dimensions,
            s2sql=s2sql,
            query_mode="LLM",
        )
    except Exception as e:
        print(f"[LLM] 解析失败: {e}")
        return None
