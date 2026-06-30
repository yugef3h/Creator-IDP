"""规则解析器：5 种查询模式 → S2SQL 生成。

匹配不到返回 None，由 llm_parser 兜底。
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from enum import Enum

import jieba

from models import SchemaElement, SemanticParseInfo


class QueryIntent(Enum):
    DISTRIBUTION = "distribution"   # 分布：单维度聚合，如"各分区分布"
    RANKING = "ranking"             # 排名/对比：维度 + 排序 + TopN
    TREND = "trend"                 # 趋势：时间序列
    CARD = "card"                   # 单值卡片
    DETAIL = "detail"               # 明细：不聚合


# 意图关键词映射
_INTENT_KEYWORDS = {
    QueryIntent.DISTRIBUTION: {"分布", "占比", "比例", "构成", "组成", "分别"},
    QueryIntent.RANKING: {"排名", "排行", "最多", "最少", "最高", "最低", "对比", "比较", "各"},
    QueryIntent.TREND: {"趋势", "走势", "变化", "每天", "每日", "最近"},
    QueryIntent.CARD: {"多少", "是多少", "怎么样", "如何"},
}


def classify_intent(query: str) -> QueryIntent:
    """根据查询关键词判断意图。"""
    scores = {intent: 0 for intent in QueryIntent}
    for intent, keywords in _INTENT_KEYWORDS.items():
        scores[intent] = sum(1 for kw in keywords if kw in query)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else QueryIntent.CARD


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _days_ago(n: int) -> str:
    return (datetime.now() - timedelta(days=n)).strftime("%Y-%m-%d")


def _last_month_start() -> str:
    today = datetime.now()
    first = today.replace(day=1) - timedelta(days=1)
    return first.replace(day=1).strftime("%Y-%m-%d")


def _last_month_end() -> str:
    today = datetime.now()
    return (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")


def _this_week_start() -> str:
    today = datetime.now()
    return (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")


def _detect_main_table(metrics: list[SchemaElement], dimensions: list[SchemaElement]) -> str:
    """根据匹配到的元素推断主表。"""
    for m in metrics:
        if m.table:
            return m.table
    for d in dimensions:
        if d.table:
            return d.table
    return "video_stats"


def _is_fans_query(metrics: list[SchemaElement], dimensions: list[SchemaElement]) -> bool:
    """判断是否只涉及 fans 表。"""
    all_elements = metrics + dimensions
    tables = set()
    for el in all_elements:
        if el.table:
            tables.add(el.table)
        elif el.join_table:
            tables.add("video_stats")  # 有跨表维度说明主表是 video_stats
    return tables == {"fans"}


def _date_column(metrics: list[SchemaElement], dimensions: list[SchemaElement]) -> str:
    """根据查询的表返回正确的日期字段名。"""
    return "follow_time" if _is_fans_query(metrics, dimensions) else "stat_date"


# 日期相关关键词
_DATE_KEYWORDS = {"最近", "今天", "昨天", "本周", "上周", "本月", "上月", "上个月",
                  "天", "周", "月", "年", "日", "近"}

# 通用停用词 + 已知城市名（用于 _has_unrecognized_content 过滤）
_STOP_WORDS = {"的", "是", "我", "帮", "吧", "呢", "吗", "啊", "了", "什么", "怎么",
               "多少", "怎么样", "如何", "一下", "一个", "哪些", "哪个", "有没有",
               "查", "看", "看看", "帮我", "我想", "想知道", "告诉我",
               "北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "重庆", "西安"}


def _has_unrecognized_content(query: str, matched_elements: list[SchemaElement],
                               date_info: dict, trie_keys: set) -> bool:
    """检查查询中是否有未被识别的实义词。

    如果有 → 规则解析不可信，拒绝回答。
    """
    tokens = [t.strip() for t in jieba.lcut(query) if len(t.strip()) >= 2]
    if not tokens:
        return False

    # 收集所有已识别的词
    recognized = set(_STOP_WORDS) | set(_DATE_KEYWORDS) | trie_keys
    for el in matched_elements:
        recognized.add(el.biz_name)
        if el.alias:
            for a in el.alias.replace("，", ",").split(","):
                recognized.add(a.strip())
    # 数字、日期中的数值
    for word in re.findall(r"\d+", query):
        recognized.add(word)

    unrecognized = [t for t in tokens if t not in recognized]
    return len(unrecognized) > 0


def parse(
    query: str,
    matched_elements: list[SchemaElement],
    trie_keys: set | None = None,
) -> SemanticParseInfo | None:
    """尝试用规则解析。成功返回 SemanticParseInfo，失败返回 None。"""
    metrics = [e for e in matched_elements if e.element_type == "METRIC"]
    dimensions = [e for e in matched_elements if e.element_type == "DIMENSION"]

    if not metrics:
        return None

    # ---------- 意图分类 ----------
    intent = classify_intent(query)

    # DISTRIBUTION 模式：去除 trie 误匹配的额外维度
    # 只保留最相关的维度（别名中最长匹配的那个）
    if intent == QueryIntent.DISTRIBUTION and len(dimensions) > 1:
        # 找查询中出现的别名关键词
        dim_scores = []
        for d in dimensions:
            score = 0
            for alias in d.alias.split(","):
                alias = alias.strip()
                if alias and len(alias) >= 2:
                    # 别名整体出现 → 高分
                    if alias in query:
                        score += len(alias) * 10
                    else:
                        # 分词看子词匹配
                        for part in jieba.lcut(alias):
                            if part in query and len(part) >= 2:
                                score += len(part)
            dim_scores.append((score, d))
        dim_scores.sort(key=lambda x: -x[0])
        # 只保留得分最高的那个维度
        if dim_scores and dim_scores[0][0] > 0:
            dimensions = [dim_scores[0][1]]

    # ---------- 日期提取 ----------
    date_info: dict = {}
    if re.search(r"最近(\d+)天|近(\d+)天|过去(\d+)天", query):
        m = re.search(r"(\d+)", query)
        n = int(m.group(1)) if m else 7
        date_info = {"start": _days_ago(n), "end": _today()}
    elif "上个月" in query or "上月" in query:
        date_info = {"start": _last_month_start(), "end": _last_month_end()}
    elif "本周" in query:
        date_info = {"start": _this_week_start(), "end": _today()}
    elif "今天" in query:
        date_info = {"start": _today(), "end": _today()}
    elif "昨天" in query:
        date_info = {"start": _days_ago(1), "end": _days_ago(1)}

    # ---------- 维度值过滤 ----------
    filters: list[dict] = []

    # 城市过滤：即使 city 维度未被匹配，也检测城市名
    cities = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "重庆", "西安"]
    for city in cities:
        if city in query:
            idx = query.index(city)
            before_ok = idx == 0 or not query[idx - 1].isalpha()
            if before_ok:
                # 查找或创建 city filter
                # 如果 city 不在 matched dimensions 中，临时添加
                city_dim = next((d for d in dimensions if d.biz_name == "city"), None)
                biz = city_dim.biz_name if city_dim else "city"
                filters.append({"biz_name": biz, "operator": "=", "value": city})
                # 确保 city 在 dimensions 中
                if not city_dim:
                    # 从所有元素中找 city（不在 matched 中但可能在 elements 里）
                    # 这里只能从 matched 中找
                    pass
                break

    for dim in dimensions:
        for alias in dim.alias.split(","):
            alias = alias.strip()
            if alias in query and len(alias) >= 2:
                # 分区过滤
                cat_match = re.search(rf"([一-鿿]{{2,4}})(?:的{alias}|{alias})", query)
                if cat_match and dim.biz_name in ("category", "video_title"):
                    val = cat_match.group(1)
                    if val not in ("城市", "地区", "地域", "性别", "年龄", "分区", "类别"):
                        filters.append({"biz_name": dim.biz_name, "operator": "=", "value": val})
                        break
        # 城市过滤：仅明确城市名
        if dim.biz_name == "city":
            cities = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "重庆", "西安"]
            for city in cities:
                if city in query:
                    idx = query.index(city)
                    before_ok = idx == 0 or not query[idx - 1].isalpha()
                    if before_ok:
                        filters.append({"biz_name": dim.biz_name, "operator": "=", "value": city})
                        break

    # ---------- TopN 提取 ----------
    limit = None
    top_match = re.search(r"最[多高]的?(\d+)?[个条]?", query)
    if top_match:
        limit = int(top_match.group(1)) if top_match.group(1) else 5

    # ---------- 主表 + 日期字段 ----------
    main_table = _detect_main_table(metrics, dimensions)
    date_col = _date_column(metrics, dimensions)
    is_fans = _is_fans_query(metrics, dimensions)

    # ---------- 模式匹配 & S2SQL 生成 ----------
    s2sql = ""
    query_mode = "RULE"
    has_date_dim = any(d.biz_name in ("stat_date", "follow_time") for d in dimensions)

    def _esc(v):
        return f"'{v}'"

    # 辅助：判断是否需要 videos JOIN
    def _needs_videos_join(dims, mets) -> bool:
        return any(d.join_table == "videos" for d in dims)

    if date_info and not has_date_dim:
        # 有日期但没有日期维度
        if dimensions:
            # 有其他维度 → METRIC_GROUPBY + 日期 WHERE 过滤
            s2sql_parts = []
            select_fields = [d.biz_name for d in dimensions]
            agg_metrics = [
                f"{m.default_agg}({m.biz_name})" if m.default_agg else m.biz_name
                for m in metrics
            ]
            select_fields.extend(agg_metrics)
            s2sql_parts.append(f"SELECT {', '.join(select_fields)}")
            s2sql_parts.append(f"FROM {main_table}")
            if _needs_videos_join(dimensions, metrics) and main_table == "video_stats":
                s2sql_parts.append("JOIN videos ON video_stats.video_id = videos.video_id")
            where_clauses = [f"{date_col} BETWEEN {_esc(date_info['start'])} AND {_esc(date_info['end'])}"]
            for f in filters:
                dim_el = next((d for d in dimensions if d.biz_name == f["biz_name"]), None)
                col = dim_el.name if dim_el else f["biz_name"]
                where_clauses.append(f"{col} = {_esc(f['value'])}")
            s2sql_parts.append("WHERE " + " AND ".join(where_clauses))
            group_cols = [d.biz_name for d in dimensions]
            s2sql_parts.append(f"GROUP BY {', '.join(group_cols)}")
            s2sql_parts.append(f"ORDER BY {agg_metrics[0]} DESC")
            s2sql = "\n".join(s2sql_parts)
            query_mode = "METRIC_GROUPBY"
        else:
            # 无其他维度 → METRIC_TREND（纯时间序列）
            s2sql_parts = []
            agg_metrics = [
                f"{m.default_agg}({m.biz_name})" if m.default_agg else m.biz_name
                for m in metrics
            ]
            s2sql_parts.append(f"SELECT {date_col}, {', '.join(agg_metrics)}")
            s2sql_parts.append(f"FROM {main_table}")
            if _needs_videos_join(dimensions, metrics):
                s2sql_parts.append("JOIN videos ON video_stats.video_id = videos.video_id")
            where_clauses = [f"{date_col} BETWEEN {_esc(date_info['start'])} AND {_esc(date_info['end'])}"]
            for f in filters:
                dim_el = next((d for d in dimensions if d.biz_name == f["biz_name"]), None)
                col = dim_el.name if dim_el else f["biz_name"]
                where_clauses.append(f"{col} = {_esc(f['value'])}")
            if where_clauses:
                s2sql_parts.append("WHERE " + " AND ".join(where_clauses))
            s2sql_parts.append(f"GROUP BY {date_col}")
            s2sql_parts.append(f"ORDER BY {date_col}")
            s2sql = "\n".join(s2sql_parts)
            query_mode = "METRIC_TREND"

    elif len(metrics) >= 1 and len(dimensions) >= 1:
        # METRIC_GROUPBY / METRIC_FILTER / METRIC_ORDERBY
        s2sql_parts = []
        select_fields = [d.biz_name for d in dimensions]
        agg_metrics = [
            f"{m.default_agg}({m.biz_name})" if m.default_agg else m.biz_name
            for m in metrics
        ]
        select_fields.extend(agg_metrics)
        s2sql_parts.append(f"SELECT {', '.join(select_fields)}")
        s2sql_parts.append(f"FROM {main_table}")

        if _needs_videos_join(dimensions, metrics) and main_table == "video_stats":
            s2sql_parts.append("JOIN videos ON video_stats.video_id = videos.video_id")

        where_clauses = []
        if date_info:
            where_clauses.append(f"{date_col} BETWEEN {_esc(date_info['start'])} AND {_esc(date_info['end'])}")
        for f in filters:
            dim_el = next((d for d in dimensions if d.biz_name == f["biz_name"]), None)
            col = dim_el.name if dim_el else f["biz_name"]
            where_clauses.append(f"{col} = {_esc(f['value'])}")
        if where_clauses:
            s2sql_parts.append("WHERE " + " AND ".join(where_clauses))

        group_cols = [d.biz_name for d in dimensions]
        s2sql_parts.append(f"GROUP BY {', '.join(group_cols)}")
        s2sql_parts.append(f"ORDER BY {agg_metrics[0]} DESC")

        if limit:
            s2sql_parts.append(f"LIMIT {limit}")

        s2sql = "\n".join(s2sql_parts)

        if filters:
            query_mode = "METRIC_FILTER"
        elif limit:
            query_mode = "METRIC_ORDERBY"
        else:
            query_mode = "METRIC_GROUPBY"

    elif len(metrics) >= 1 and not dimensions and not date_info:
        # METRIC_CARD：单指标，无维度无日期
        # 安全检查：查询中有未识别实义词 → 不自动回答，交给 LLM
        if _has_unrecognized_content(query, matched_elements, date_info, trie_keys or set()):
            return None
        agg_metrics = [
            f"{m.default_agg}({m.biz_name})" if m.default_agg else m.biz_name
            for m in metrics
        ]
        s2sql_parts = [f"SELECT {', '.join(agg_metrics)}"]
        s2sql_parts.append(f"FROM {main_table}")
        # 应用维度过滤（如城市）
        where_clauses = []
        for f in filters:
            col = f["biz_name"]  # 直接用 biz_name 作为列名（如 city）
            where_clauses.append(f"{col} = {_esc(f['value'])}")
        if where_clauses:
            s2sql_parts.append("WHERE " + " AND ".join(where_clauses))
        s2sql = "\n".join(s2sql_parts)
        query_mode = "METRIC_CARD"

    else:
        return None

    return SemanticParseInfo(
        metrics=metrics,
        dimensions=dimensions,
        filters=filters,
        date_info=date_info,
        s2sql=s2sql,
        query_mode=query_mode,
    )
