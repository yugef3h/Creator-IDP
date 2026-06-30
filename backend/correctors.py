"""Corrector Chain：S2SQL 修正。

在 Translate 之前执行，修正 LLM/规则生成 S2SQL 的常见问题。
V1.0 新增模块。
"""

from __future__ import annotations

from models import SchemaElement, SemanticParseInfo


def correct(parse_info: SemanticParseInfo, schema_elements: list[SchemaElement]) -> SemanticParseInfo:
    """链式执行所有 corrector。"""
    parse_info = _schema_correct(parse_info, schema_elements)
    parse_info = _grammar_correct(parse_info)
    parse_info = _time_correct(parse_info)
    return parse_info


def _schema_correct(parse_info: SemanticParseInfo, elements: list[SchemaElement]) -> SemanticParseInfo:
    """验证 S2SQL 中的字段都在 schema 中，修正拼写错误。"""
    s2sql = parse_info.s2sql
    valid_names = {e.biz_name for e in elements}

    # 提取 SQL 中的标识符
    import re
    identifiers = set(re.findall(r'\b([a-zA-Z_]\w*)\b', s2sql))

    for ident in identifiers:
        if ident.lower() in ("select", "from", "where", "group", "by", "order",
                              "and", "or", "join", "on", "as", "desc", "asc",
                              "limit", "between", "in", "not", "null", "nullif",
                              "sum", "avg", "count", "max", "min", "distinct",
                              "inner", "left", "right", "outer", "like",
                              "videos", "video_stats", "fans"):  # 表名不修正
            continue
        if ident not in valid_names:
            # 尝试编辑距离修正
            for name in valid_names:
                if _edit_distance(ident, name) <= 2:
                    s2sql = s2sql.replace(ident, name)
                    print(f"  [SchemaCorrector] {ident} → {name}")
                    break

    parse_info.s2sql = s2sql
    return parse_info


def _grammar_correct(parse_info: SemanticParseInfo) -> SemanticParseInfo:
    """语法修正：确保聚合函数、GROUP BY 正确。"""
    s2sql = parse_info.s2sql
    sql_upper = s2sql.upper()

    # 有聚合函数但无 GROUP BY？检查 SELECT 中是否有非聚合字段
    has_agg = any(f in sql_upper for f in ["SUM(", "AVG(", "COUNT(", "MAX(", "MIN("])
    has_group_by = "GROUP BY" in sql_upper

    if has_agg and not has_group_by:
        # 查找 SELECT 中的非聚合字段（不含括号的标识符）
        import re
        select_part = re.search(r'SELECT(.+?)FROM', s2sql, re.IGNORECASE | re.DOTALL)
        if select_part:
            fields = [f.strip() for f in select_part.group(1).split(",")]
            non_agg_fields = [f for f in fields if "(" not in f]
            # 只有在有非聚合维度字段时才需要 GROUP BY
            if non_agg_fields and len(fields) > len(non_agg_fields):
                s2sql = s2sql.rstrip().rstrip(";").strip()
                s2sql += f"\nGROUP BY {', '.join(non_agg_fields)}"
                print(f"  [GrammarCorrector] added GROUP BY {non_agg_fields}")

    parse_info.s2sql = s2sql
    return parse_info


def _time_correct(parse_info: SemanticParseInfo) -> SemanticParseInfo:
    """日期修正：有 date_info 但 SQL 缺少 WHERE → 补充。"""
    s2sql = parse_info.s2sql
    sql_upper = s2sql.upper()

    if parse_info.date_info and "WHERE" not in sql_upper:
        start = parse_info.date_info.get("start", "")
        end = parse_info.date_info.get("end", "")
        if start and end:
            # 在 GROUP BY / ORDER BY / LIMIT 之前插入 WHERE
            if "GROUP BY" in sql_upper:
                s2sql = s2sql.replace("GROUP BY", f"WHERE stat_date BETWEEN '{start}' AND '{end}' GROUP BY")
            elif "ORDER BY" in sql_upper:
                s2sql = s2sql.replace("ORDER BY", f"WHERE stat_date BETWEEN '{start}' AND '{end}' ORDER BY")
            elif "LIMIT" in sql_upper:
                s2sql = s2sql.replace("LIMIT", f"WHERE stat_date BETWEEN '{start}' AND '{end}' LIMIT")
            else:
                s2sql = s2sql.rstrip() + f"\nWHERE stat_date BETWEEN '{start}' AND '{end}'"
            print(f"  [TimeCorrector] added WHERE date between {start} and {end}")

    parse_info.s2sql = s2sql
    return parse_info


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein 编辑距离。"""
    if len(a) < len(b):
        return _edit_distance(b, a)
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(
                prev[j + 1] + 1,   # delete
                curr[j] + 1,        # insert
                prev[j] + (ca != cb)  # substitute
            ))
        prev = curr
    return prev[-1]
