"""Trie 索引：jieba 分词 + 前缀/后缀匹配，从用户输入中识别 Schema 元素。"""

from __future__ import annotations

import jieba
from models import SchemaElement

# 高频通用词黑名单：不索引这些词，避免误匹配
_BLACKLIST = {"分布", "排名", "趋势", "统计", "分析", "情况", "数据", "信息",
              "比例", "对比", "关系", "变化", "走势", "汇总", "总览", "详情"}


def build_index(elements: list[SchemaElement]) -> dict[str, list[SchemaElement]]:
    """构建倒排索引：{token: [SchemaElement, ...]}，过滤单字 token。"""
    index: dict[str, list[SchemaElement]] = {}
    for el in elements:
        # 分词 biz_name
        for token in jieba.lcut(el.biz_name):
            token = token.strip().lower()
            if len(token) >= 2 and token not in _BLACKLIST:
                index.setdefault(token, []).append(el)
        # 分词 alias
        if el.alias:
            for alias_part in el.alias.replace("，", ",").split(","):
                for token in jieba.lcut(alias_part.strip()):
                    token = token.strip().lower()
                    if len(token) >= 2 and token not in _BLACKLIST:
                        index.setdefault(token, []).append(el)
    return index


def match(query: str, index: dict[str, list[SchemaElement]]) -> list[SchemaElement]:
    """匹配用户查询中的 Schema 元素，去重返回。"""
    tokens = jieba.lcut(query)
    matched: dict[int, SchemaElement] = {}  # element_id → element

    for token in tokens:
        token = token.strip().lower()
        if len(token) < 2 or token in _BLACKLIST:
            continue
        # 精确匹配
        if token in index:
            for el in index[token]:
                matched[el.id] = el
        # 后缀/前缀匹配（补充）
        for key, els in index.items():
            if key == token:
                continue
            if token.endswith(key) or key.endswith(token) or token.startswith(key) or key.startswith(token):
                for el in els:
                    if el.element_type == "DIMENSION":
                        matched[el.id] = el
    return list(matched.values())


def extract_metrics(elements: list[SchemaElement]) -> list[SchemaElement]:
    return [e for e in elements if e.element_type == "METRIC"]


def extract_dimensions(elements: list[SchemaElement]) -> list[SchemaElement]:
    return [e for e in elements if e.element_type == "DIMENSION"]
