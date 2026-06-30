"""执行器：SQLite 执行物理 SQL → QueryResult，含自动聚合兜底。"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from models import ColumnInfo, QueryResult


def infer_type(value: str | None, col_name: str) -> str:
    """推断列的数据类型。"""
    if col_name.lower() in ("stat_date", "publish_time", "follow_time", "日期", "时间"):
        return "DATE"
    if value is None:
        return "CATEGORY"
    try:
        float(value)
        return "NUMERIC"
    except (ValueError, TypeError):
        return "CATEGORY"


def _detect_over_granularity(columns: list[ColumnInfo], rows: list[tuple]) -> bool:
    """检测结果是否粒度过细：同一维度值出现多次暗示多余 GROUP BY。"""
    if len(rows) <= 20:
        return False  # 少量行不需要聚合
    # 找第一个 CATEGORY 列，检查是否有重复值
    for i, col in enumerate(columns):
        if col.show_type == "CATEGORY":
            vals = [row[i] for row in rows]
            if len(vals) != len(set(vals)):
                return True  # 分类列有重复 → 粒度过细
    return False


def _auto_aggregate(columns: list[ColumnInfo], rows: list[tuple]) -> QueryResult:
    """自动聚合：按第一个 CATEGORY 列 GROUP BY，NUMERIC 列 SUM。

    丢弃其他维度的多余列（粒度过细的产物）。
    """
    cat_idx = next((i for i, c in enumerate(columns) if c.show_type == "CATEGORY"), 0)
    num_indices = [i for i, c in enumerate(columns) if c.show_type == "NUMERIC"]
    # 保留的列：分类列 + 数值列，丢弃多余的 CATEGORY/DATE 列
    keep_indices = [cat_idx] + num_indices

    grouped: dict[str, list[float]] = defaultdict(lambda: [0.0] * len(num_indices))
    for row in rows:
        key = str(row[cat_idx])
        for j, ni in enumerate(num_indices):
            try:
                grouped[key][j] += float(row[ni]) if row[ni] is not None else 0
            except (ValueError, TypeError):
                pass

    new_cols = [columns[i] for i in keep_indices]
    new_rows = []
    for key, sums in sorted(grouped.items(), key=lambda x: -sum(x[1])):
        r = [key]
        for s in sums:
            r.append(int(s) if s == int(s) else round(s, 4))
        new_rows.append(tuple(r))

    print(f"  [AutoAggregate] {len(rows)} rows → {len(new_rows)} rows (按 {columns[cat_idx].name} 聚合，丢弃多余列)")
    return QueryResult(columns=new_cols, rows=new_rows)


def execute(physical_sql: str, db_path: str = "bilibili_demo.db") -> QueryResult:
    """执行物理 SQL，返回 QueryResult。"""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(physical_sql)
    col_names = [d[0] for d in cursor.description] if cursor.description else []
    rows = cursor.fetchall()
    conn.close()

    # 推断列类型（取第一行数据）
    columns = []
    if rows:
        for i, name in enumerate(col_names):
            columns.append(ColumnInfo(name=name, show_type=infer_type(rows[0][i], name)))
    else:
        columns = [ColumnInfo(name=n, show_type="CATEGORY") for n in col_names]

    # 自动聚合兜底：检测到粒度过细 → 聚合
    result = QueryResult(columns=columns, rows=rows, sql=physical_sql)
    if _detect_over_granularity(columns, rows):
        result = _auto_aggregate(columns, rows)
        result.sql = physical_sql  # 保留原始 SQL 供展示

    return result
