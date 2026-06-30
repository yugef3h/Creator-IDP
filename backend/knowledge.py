"""Layer 3: Pure Knowledge Q&A — 术语/指标定义查询，不执行 SQL。

当用户问 "三连是什么"、"互动率怎么算" 时，匹配 dataset.yaml 中的
terms/metrics 定义，直接返回描述，不走 SQL 链路。
"""

from __future__ import annotations

import re
import yaml
from typing import Optional


def load_knowledge_base() -> dict:
    """加载知识库：{关键词: {text, type}}。"""
    with open("dataset.yaml", "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    kb = {}
    ds = raw["datasets"][0]

    # 指标 → 定义
    for m in ds.get("metrics", []):
        text = f"**{m['biz_name']}**（{m.get('alias', '')}）：{m.get('description', '')}"
        if m.get("expression"):
            text += f"\n\n计算公式：`{m['expression']}`"
        if m.get("default_agg"):
            text += f"\n默认聚合：{m['default_agg']}"
        kb[m["biz_name"]] = {"text": text, "type": "metric"}
        # 中文别名也映射
        if m.get("alias"):
            for alias in m["alias"].replace("，", ",").split(","):
                a = alias.strip()
                if a and len(a) >= 2:
                    kb[a] = {"text": text, "type": "metric"}

    # 术语 → 定义
    for t in ds.get("terms", []):
        text = f"**{t['name']}**：{t.get('description', '')}"
        kb[t["name"]] = {"text": text, "type": "term"}
        if t.get("alias"):
            for alias in t["alias"].replace("，", ",").split(","):
                a = alias.strip()
                if a and len(a) >= 2:
                    kb[a] = {"text": text, "type": "term"}

    return kb


# 知识类查询模式（仅匹配明确的定义类问题，避免与数据查询冲突）
_KNOWLEDGE_PATTERNS = [
    r"什么是(.+)",
    r"(.+)是什么",
    r"(.+)怎么算",
    r"(.+)的定义",
    r"(.+)的定义是什么",
    r"(.+)公式",
    r"(.+)是什么意思",
    r"(.+)指什么",
    r"(.+)的含义",
    r"解释一下(.+)",
]


def match_knowledge(query: str) -> Optional[dict]:
    """匹配知识类查询，返回 {text, type, term}。不匹配返回 None。"""
    kb = load_knowledge_base()

    # 先尝试正则提取用户问的术语名
    for pattern in _KNOWLEDGE_PATTERNS:
        m = re.search(pattern, query)
        if m:
            term = m.group(1).strip()
            # 在知识库中查找
            if term in kb:
                entry = kb[term]
                return {
                    "text": entry["text"],
                    "type": entry["type"],
                    "term": term,
                }
            # 模糊匹配：用户说 "三连" 匹配 term "三连"
            for key, entry in kb.items():
                if term in key or key in term:
                    return {
                        "text": entry["text"],
                        "type": entry["type"],
                        "term": key,
                    }

    # 直接匹配：仅术语（非指标）短查询时触发。指标走 NL2SQL
    if len(query) <= 8:
        for key, entry in kb.items():
            if key in query and len(key) >= 2 and entry["type"] == "term":
                return {
                    "text": entry["text"],
                    "type": entry["type"],
                    "term": key,
                }

    return None
