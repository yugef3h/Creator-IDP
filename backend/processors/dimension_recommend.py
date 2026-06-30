"""DimensionRecommendProcessor：下钻维度推荐。

根据当前查询使用的维度和指标，推荐未使用的关联维度。
"""

from __future__ import annotations

from models import SchemaElement

# 指标 → 可下钻的关联维度
_METRIC_DRILL_DIMS: dict[str, list[str]] = {
    "views": ["category", "video_title", "stat_date", "duration"],
    "likes": ["category", "video_title", "stat_date"],
    "coins": ["category", "video_title", "stat_date"],
    "favorites": ["category", "video_title", "stat_date"],
    "danmaku": ["category", "video_title", "stat_date"],
    "comments": ["category", "video_title", "stat_date"],
    "shares": ["category", "video_title", "stat_date"],
    "interaction_rate": ["category", "duration", "stat_date"],
    "coin_rate": ["category", "duration", "stat_date"],
    "fan_count": ["gender", "age_group", "city"],
}

# 维度 → 可下钻的更深维度
_DIM_DRILL_DIMS: dict[str, list[str]] = {
    "category": ["video_title", "duration"],
    "city": ["gender", "age_group"],
    "gender": ["age_group", "city"],
    "age_group": ["gender", "city"],
}


def recommend(
    metrics: list[SchemaElement],
    dimensions: list[SchemaElement],
    max_count: int = 5,
) -> list[dict]:
    """推荐未使用的下钻维度。"""
    used_dims = {d.biz_name for d in dimensions}
    candidates: dict[str, float] = {}  # biz_name → score

    # 从指标推荐
    for m in metrics:
        for dim_name in _METRIC_DRILL_DIMS.get(m.biz_name, []):
            if dim_name not in used_dims:
                candidates[dim_name] = candidates.get(dim_name, 0) + 1

    # 从已有维度推荐更深维度
    for d in dimensions:
        for dim_name in _DIM_DRILL_DIMS.get(d.biz_name, []):
            if dim_name not in used_dims:
                candidates[dim_name] = candidates.get(dim_name, 0) + 2  # 更深维度权重更高

    # 排序取 top-N
    sorted_dims = sorted(candidates.items(), key=lambda x: -x[1])[:max_count]
    return [{"biz_name": name, "score": score} for name, score in sorted_dims]
