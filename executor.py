"""执行器：SQLite 执行物理 SQL → QueryResult。"""

from __future__ import annotations

import sqlite3
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

    return QueryResult(columns=columns, rows=rows, sql=physical_sql)
