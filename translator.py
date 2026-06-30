"""翻译器：S2SQL（bizName）→ 物理 SQL（物理列名/表达式 + JOIN + LIMIT）。

确定性代码，不经过 LLM——这是防幻觉的核心。
"""

from __future__ import annotations

import re
import yaml


def _load_schema() -> dict:
    with open("dataset.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_lookup() -> dict[str, dict]:
    """构建 bizName → element 字典。"""
    schema = _load_schema()
    lookup = {}
    for ds in schema["datasets"]:
        for m in ds.get("metrics", []):
            lookup[m["biz_name"]] = {"type": "metric", **m}
        for d in ds.get("dimensions", []):
            lookup[d["biz_name"]] = {"type": "dimension", **d}
    return lookup


def translate(s2sql: str) -> str:
    """将 S2SQL 翻译为物理 SQL。

    处理：
    1. 派生指标的 AGG(bizName) → AGG(expression)
    2. 普通指标的 AGG(bizName) → AGG(physical_name)
    3. 裸 bizName（无聚合包裹）→ 添加默认聚合
    4. 维度 bizName → physical_name
    5. 添加 JOIN
    6. 修复 fans 表的日期字段名
    7. 添加 LIMIT
    """
    lookup = _build_lookup()
    sql = s2sql.strip()

    agg_funcs = ["SUM", "COUNT", "AVG", "MAX", "MIN"]

    # 收集所有 bizName
    biz_names_in_sql: set[str] = set()
    for biz_name in lookup:
        if biz_name in sql:
            biz_names_in_sql.add(biz_name)

    # 处理排序：长名优先，派生指标优先
    sorted_names = sorted(biz_names_in_sql, key=lambda x: (-len(x), x))

    # ---------- Step 1: 替换 AGG(bizName) 模式 ----------
    for biz_name in sorted_names:
        el = lookup[biz_name]
        if el["type"] != "metric":
            continue

        if el.get("expression"):
            expr = el["expression"]
            for func in agg_funcs:
                pattern = f"{func}({biz_name})"
                if pattern in sql:
                    # 替换整个 AGG(bizName)，保留 AGG(expr)
                    sql = sql.replace(pattern, f"{func}({expr})")
        else:
            phys = el["name"]
            for func in agg_funcs:
                pattern = f"{func}({biz_name})"
                if pattern in sql:
                    sql = sql.replace(pattern, f"{func}({phys})")

    # ---------- Step 2: 替换裸 bizName（未被聚合包裹的） ----------
    for biz_name in sorted_names:
        el = lookup[biz_name]
        if el["type"] != "metric":
            continue

        # 检查是否有任何 AGG(biz_name) 模式已存在
        already_wrapped = any(f"{f}({biz_name})" in sql for f in agg_funcs)

        if not already_wrapped and biz_name in sql:
            # 裸 bizName，添加默认聚合
            agg = el.get("default_agg", "")
            phys = el.get("expression") or el["name"]
            if agg:
                sql = sql.replace(biz_name, f"{agg}({phys})")
            else:
                sql = sql.replace(biz_name, phys or biz_name)

    # ---------- Step 3: 替换维度 bizName ----------
    for biz_name in sorted_names:
        el = lookup[biz_name]
        if el["type"] == "dimension":
            # 用 word boundary 替换，避免替换已含表前缀的引用
            sql = re.sub(rf'\b{re.escape(biz_name)}\b', el["name"], sql)

    # ---------- Step 4: 修复 fans 表的日期字段 ----------
    # 如果 FROM 是 fans 表，把 stat_date 替换为 follow_time
    if "FROM fans" in sql and "stat_date" in sql:
        sql = sql.replace("stat_date", "follow_time")

    # ---------- Step 5: 收集 JOIN ----------
    join_tables: dict[str, str] = {}
    for biz_name in biz_names_in_sql:
        el = lookup[biz_name]
        if el.get("join_table") and el.get("join_key"):
            join_tables[el["join_table"]] = el["join_key"]

    # ---------- Step 6: 处理主表 + JOIN ----------
    # 从数据集配置中获取主表
    schema = _load_schema()
    main_table = schema["datasets"][0].get("table_name", "video_stats")

    # 检查 SQL 中的 FROM 子句
    for table in ["video_stats", "fans"]:
        if f"FROM {table}" in sql:
            for join_table, join_key in join_tables.items():
                if f"JOIN {join_table}" not in sql:
                    sql = sql.replace(
                        f"FROM {table}",
                        f"FROM {table} JOIN {join_table} ON {join_key}"
                    )
            break

    # ---------- Step 7: LIMIT ----------
    if "LIMIT" not in sql.upper():
        sql = f"{sql} LIMIT 1000"

    return sql
