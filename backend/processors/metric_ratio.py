"""MetricRatioCalcProcessor：环比/同比自动计算。

查询上一周期数据，计算增长率。作为 SSE done 事件的附加数据返回。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from models import SemanticParseInfo


def calc_ratio(parse_info: SemanticParseInfo, db_path: str = "bilibili_demo.db") -> dict | None:
    """计算当前周期相对于上一周期的变化率。

    返回 {metric_name: {current, previous, ratio, label}}，失败返回 None。
    """
    date_info = parse_info.date_info
    if not date_info or not date_info.get("start") or not date_info.get("end"):
        return None

    try:
        current_start = datetime.strptime(date_info["start"], "%Y-%m-%d")
        current_end = datetime.strptime(date_info["end"], "%Y-%m-%d")
    except ValueError:
        return None

    period_days = (current_end - current_start).days + 1
    if period_days < 1:
        return None

    # 前一个周期
    prev_start = (current_start - timedelta(days=period_days)).strftime("%Y-%m-%d")
    prev_end = (current_start - timedelta(days=1)).strftime("%Y-%m-%d")

    # 确定周期标签
    if period_days <= 1:
        label = "日环比"
    elif period_days <= 10:
        label = "周环比"
    elif period_days <= 35:
        label = "月环比"
    else:
        label = "同比"

    # 对每个指标查询上一周期
    conn = sqlite3.connect(db_path)
    ratios = {}

    for metric in parse_info.metrics:
        col = metric.name or metric.biz_name
        agg = metric.default_agg or "SUM"

        # 当前值
        try:
            if metric.table:
                # 跨表指标（如 fan_count）
                cur = conn.execute(
                    f"SELECT {agg}({col}) FROM {metric.table} WHERE follow_time BETWEEN ? AND ?",
                    (date_info["start"], date_info["end"])
                ).fetchone()[0] or 0
                prev = conn.execute(
                    f"SELECT {agg}({col}) FROM {metric.table} WHERE follow_time BETWEEN ? AND ?",
                    (prev_start, prev_end)
                ).fetchone()[0] or 0
            else:
                cur = conn.execute(
                    f"SELECT {agg}({col}) FROM video_stats WHERE stat_date BETWEEN ? AND ?",
                    (date_info["start"], date_info["end"])
                ).fetchone()[0] or 0
                prev = conn.execute(
                    f"SELECT {agg}({col}) FROM video_stats WHERE stat_date BETWEEN ? AND ?",
                    (prev_start, prev_end)
                ).fetchone()[0] or 0
        except Exception:
            continue

        if prev and prev != 0:
            ratio = (cur - prev) / prev
        else:
            ratio = 0

        ratios[metric.biz_name] = {
            "current": cur,
            "previous": prev,
            "ratio": round(ratio, 4),
            "label": label,
        }

    conn.close()
    return ratios if ratios else None
