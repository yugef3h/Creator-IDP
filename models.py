"""ChatBI 核心数据模型。

V0.1 和 V1.0 共用，一次定义两版本通用。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SchemaElement:
    """指标/维度/术语的元数据。"""
    id: int
    biz_name: str          # 业务名（"views"），LLM 生成的 S2SQL 中使用的名字
    name: Optional[str]     # 物理列名（"views"），None 表示派生指标
    alias: str             # 中文别名（"播放量,播放数"），用于 Trie 匹配
    description: str       # 描述，注入 LLM prompt
    data_type: str         # "NUMERIC" | "DATE" | "CATEGORY"
    default_agg: str       # "SUM" | "COUNT" | "AVG" | ""
    expression: Optional[str] = None      # 派生指标公式
    join_table: Optional[str] = None      # 跨表维度
    join_key: Optional[str] = None        # JOIN 条件
    table: Optional[str] = None           # 所属表（fans 维度用）
    element_type: str = "METRIC"       # "METRIC" | "DIMENSION" | "TERM"


@dataclass
class SemanticParseInfo:
    """一轮查询的解析结果——所有层的桥梁。"""
    metrics: list[SchemaElement] = field(default_factory=list)
    dimensions: list[SchemaElement] = field(default_factory=list)
    filters: list[dict] = field(default_factory=list)     # [{biz_name, operator, value}]
    date_info: dict = field(default_factory=dict)          # {start: "2025-06-23", end: "2025-06-30"}
    s2sql: str = ""           # 规则/LLM 生成的语义 SQL
    query_sql: str = ""       # 翻译后的物理 SQL
    query_mode: str = ""      # "RULE" | "LLM"
    dataset_id: int = 1


@dataclass
class ColumnInfo:
    """查询结果列信息。"""
    name: str
    show_type: str  # "DATE" | "NUMERIC" | "CATEGORY"


@dataclass
class QueryResult:
    """查询执行结果 → 前端渲染。"""
    columns: list[ColumnInfo] = field(default_factory=list)
    rows: list[tuple] = field(default_factory=list)
    sql: str = ""
    parse_info: Optional[SemanticParseInfo] = None
    text_summary: Optional[str] = None
