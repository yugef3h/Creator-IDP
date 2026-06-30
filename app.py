"""ChatBI V0.1 — B站创作者视频数据中心。

Streamlit 单文件，集成 NL → S2SQL → Physical SQL → 图表。
启动：streamlit run app.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import pandas as pd
import streamlit as st
import yaml
from dotenv import load_dotenv

from executor import execute
from models import SchemaElement, SemanticParseInfo, QueryResult
from trie_index import build_index, match
from rule_parser import parse as rule_parse
from translator import translate

load_dotenv()

# ============================================================
# 初始化
# ============================================================
st.set_page_config(page_title="B站创作数据中心", page_icon="📊", layout="wide")
st.title("📊 B站创作数据中心")
st.caption("用自然语言查询你的视频数据——试试输入下面的问题 👇")

# 加载 schema
@st.cache_resource
def load_schema_elements() -> list[SchemaElement]:
    with open("dataset.yaml", "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    elements = []
    ds = raw["datasets"][0]
    for m in ds.get("metrics", []):
        elements.append(SchemaElement(
            id=m["id"], biz_name=m["biz_name"], name=m.get("name"),
            alias=m.get("alias", ""), description=m.get("description", ""),
            data_type=m.get("data_type", "NUMERIC"),
            default_agg=m.get("default_agg", ""),
            expression=m.get("expression"),
            table=m.get("table"),
            element_type="METRIC",
        ))
    for d in ds.get("dimensions", []):
        elements.append(SchemaElement(
            id=d["id"], biz_name=d["biz_name"], name=d.get("name"),
            alias=d.get("alias", ""), description=d.get("description", ""),
            data_type=d.get("data_type", "CATEGORY"),
            default_agg="",
            join_table=d.get("join_table"),
            join_key=d.get("join_key"),
            table=d.get("table"),
            element_type="DIMENSION",
        ))
    return elements


ELEMENTS = load_schema_elements()
INDEX = build_index(ELEMENTS)
TRIE_KEYS = set(INDEX.keys())  # 传给 rule_parser 用于幻觉检测

# 示例问题
EXAMPLES = [
    "最近7天播放量趋势",
    "各分区播放量排名",
    "点赞最多的5个视频",
    "互动率是多少",
    "最近30天新增粉丝的城市分布",
    "各城市粉丝分步占比，用饼图",
    "帮我预测下周播放量",
]

# ============================================================
# 会话状态
# ============================================================
if "messages" not in st.session_state:
    st.session_state.messages = []

# ============================================================
# 侧边栏：示例问题 + Schema 信息
# ============================================================
with st.sidebar:
    st.header("💡 试试这些")
    for ex in EXAMPLES:
        if st.button(ex, key=f"ex_{ex}", use_container_width=True):
            st.session_state.pending_query = ex
            st.rerun()

    st.divider()
    st.header("📋 数据概览")
    st.caption(f"• 50 个视频，8 个分区")
    st.caption(f"• 9 个指标，7 个维度")
    st.caption(f"• 数据范围：最近 90 天")

    st.divider()
    st.caption("Powered by DeepSeek V3 | SQLite | Streamlit")

# ============================================================
# 处理查询
# ============================================================
def process_query(query: str) -> tuple[SemanticParseInfo | None, QueryResult | None, str]:
    """处理用户查询：匹配 → 解析 → 翻译 → 执行。"""
    # 1. Trie 匹配
    matched = match(query, INDEX)
    if not matched:
        return None, None, "❌ 未识别到任何指标或维度，请尝试：播放量、点赞数、分区、日期..."

    # 2. 解析（仅规则解析，不做 LLM 兜底——杜绝幻觉）
    parse_info = rule_parse(query, matched, TRIE_KEYS)
    if parse_info is None or not parse_info.s2sql:
        return None, None, "抱歉，我无法理解这个问题。请尝试：最近7天播放量趋势、各分区播放量排名、点赞最多的5个视频"

    # 3. 翻译
    try:
        physical_sql = translate(parse_info.s2sql)
        parse_info.query_sql = physical_sql
    except Exception as e:
        return parse_info, None, f"❌ SQL 翻译失败: {e}"

    # 4. 执行
    try:
        result = execute(physical_sql)
        result.parse_info = parse_info
        return parse_info, result, ""
    except Exception as e:
        return parse_info, None, f"❌ 查询执行失败: {e}"


def render_result(parse_info: SemanticParseInfo, result: QueryResult):
    """渲染查询结果：图表 + 表格。"""
    if result is None or not result.rows:
        st.info("📭 查询结果为空")
        return

    cols = result.columns
    df = pd.DataFrame(result.rows, columns=[c.name for c in cols])

    # 图表自动选择
    num_cols = [c for c in cols if c.show_type == "NUMERIC"]
    date_cols = [c for c in cols if c.show_type == "DATE"]
    cat_cols = [c for c in cols if c.show_type == "CATEGORY"]
    n = len(df)

    # 尝试选择图表
    chart_type = None
    if n == 1 and len(num_cols) == 1 and len(cat_cols) == 0:
        chart_type = "METRIC_CARD"
    elif len(date_cols) >= 1 and len(num_cols) >= 1:
        chart_type = "METRIC_TREND"
    elif len(cat_cols) >= 1 and len(num_cols) == 1 and n <= 10:
        # 检查是否非负
        try:
            all_non_neg = (df[num_cols[0].name] >= 0).all()
        except Exception:
            all_non_neg = False
        if all_non_neg:
            chart_type = "METRIC_PIE"
        else:
            chart_type = "METRIC_BAR"
    elif len(cat_cols) >= 1 and len(num_cols) >= 1 and n <= 50:
        chart_type = "METRIC_BAR"
    else:
        chart_type = "TABLE"

    # 渲染
    if chart_type == "METRIC_CARD":
        val = df.iloc[0, 0]
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.metric(label=df.columns[0], value=f"{val:,.0f}" if isinstance(val, (int, float)) else val)
    elif chart_type == "METRIC_TREND":
        date_col_name = date_cols[0].name
        metric_col = num_cols[0].name
        chart_df = df.set_index(date_col_name)[[metric_col]]
        st.line_chart(chart_df)
    elif chart_type == "METRIC_BAR":
        cat_col_name = cat_cols[0].name
        metric_col = num_cols[0].name
        chart_df = df.set_index(cat_col_name)[[metric_col]]
        st.bar_chart(chart_df)
    elif chart_type == "METRIC_PIE":
        cat_col_name = cat_cols[0].name
        metric_col = num_cols[0].name
        chart_df = df.set_index(cat_col_name)[[metric_col]]
        st.bar_chart(chart_df)  # Streamlit 无原生 pie，用 bar 代替
    else:
        pass  # TABLE 下面统一处理

    # 始终显示表格
    with st.expander("📋 查看数据表", expanded=(chart_type == "TABLE")):
        st.dataframe(df, use_container_width=True)


# ============================================================
# 聊天界面
# ============================================================
# 显示历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sql" in msg:
            with st.expander("🔍 查看生成的 SQL"):
                st.code(msg["sql"], language="sql")

# 输入框
query = st.chat_input("输入你的问题，如：最近7天播放量趋势")
if "pending_query" in st.session_state:
    query = st.session_state.pop("pending_query")

if query:
    # 用户消息
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    # 处理查询
    with st.spinner("🔍 解析中..."):
        parse_info, result, error = process_query(query)

    # 助手回复
    with st.chat_message("assistant"):
        if error:
            st.error(error)
            st.session_state.messages.append({"role": "assistant", "content": error})
        elif parse_info and result:
            # 显示意图解析
            mode_label = {"RULE": "规则匹配", "LLM": "AI 理解", "METRIC_GROUPBY": "分组查询",
                          "METRIC_FILTER": "条件过滤", "METRIC_ORDERBY": "TopN排序",
                          "METRIC_TREND": "趋势分析", "METRIC_CARD": "单值查询"}
            mode = mode_label.get(parse_info.query_mode, parse_info.query_mode)

            metrics_str = ", ".join(m.biz_name for m in parse_info.metrics)
            dims_str = ", ".join(d.biz_name for d in parse_info.dimensions)
            date_str = ""
            if parse_info.date_info:
                date_str = f" | 📅 {parse_info.date_info.get('start', '')} ~ {parse_info.date_info.get('end', '')}"

            st.caption(f"✅ 解析模式：{mode} | 📊 指标：{metrics_str} | 📏 维度：{dims_str}{date_str}")

            # 渲染图表
            render_result(parse_info, result)

            # 显示 SQL
            with st.expander("🔍 查看生成的 SQL"):
                st.code(result.sql, language="sql")

            content = f"查询完成，返回 {len(result.rows)} 条数据。"
            st.session_state.messages.append({
                "role": "assistant",
                "content": content,
                "sql": result.sql,
            })
        else:
            st.info("请尝试输入示例问题，或换一种说法。")
