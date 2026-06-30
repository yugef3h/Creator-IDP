"""生成 B站创作者视频演示数据。

一键运行：python generate_data.py
输出：
  - bilibili_demo.db   SQLite 数据库（videos, video_stats, fans）
  - dataset.yaml       语义模型定义（指标/维度/术语）
  - exemplars.json      few-shot 示例（≥15 条）
"""

import json
import random
import sqlite3
from datetime import datetime, timedelta

import yaml

# ============================================================
# 配置
# ============================================================
random.seed(42)

CATEGORIES = ["知识", "生活", "游戏", "音乐", "动画", "科技", "美食", "时尚"]
GENDERS = ["男", "女"]
AGE_GROUPS = ["18岁以下", "18-24", "25-30", "31-40", "40岁以上"]
CITIES = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "重庆", "西安"]

VIDEO_TITLES = [
    "深入理解React Hooks原理", "Vue3源码分析系列", "我的极简桌面setup",
    "某游戏新手入门攻略", "某游戏高分局解说", "翻唱某流行歌曲",
    "一周穿搭分享", "程序员日常vlog", "某动画深度解析",
    "30天学会Python", "深圳美食探店", "机械键盘评测",
    "MacBook生产力配置", "年度书单推荐", "某科技新品开箱",
    "高考数学冲刺指南", "家常菜教学", "手绘插画教程",
    "某电影深度解读", "健身入门指南",
]

# ============================================================
# 1. 视频维度表
# ============================================================
videos = []
for i in range(1, 51):
    cat = random.choice(CATEGORIES)
    videos.append({
        "video_id": i,
        "title": f"{random.choice(VIDEO_TITLES)} #{i}",
        "category": cat,
        "duration": random.randint(60, 3600),
        "publish_time": (datetime.now() - timedelta(days=random.randint(7, 365))).strftime("%Y-%m-%d"),
    })

# ============================================================
# 2. 每日统计事实表（核心查询表）
# ============================================================
video_stats = []
start_date = datetime.now() - timedelta(days=90)

for video in videos:
    base_views = random.lognormvariate(8, 1.5)
    for day_offset in range(90):
        date = start_date + timedelta(days=day_offset)
        if date.strftime("%Y-%m-%d") < video["publish_time"]:
            continue

        weekend_boost = 1.3 if date.weekday() >= 5 else 1.0
        daily_views = max(0, int(
            random.gauss(0, 1) * base_views * 0.1 + base_views * 0.03 * weekend_boost
        ))
        if daily_views == 0:
            continue

        rate_likes = random.uniform(0.03, 0.08)
        rate_coins = random.uniform(0.01, 0.04)
        rate_fav = random.uniform(0.02, 0.06)
        rate_share = random.uniform(0.005, 0.02)
        rate_danmaku = random.uniform(0.01, 0.05)
        rate_comment = random.uniform(0.005, 0.03)

        video_stats.append({
            "video_id": video["video_id"],
            "stat_date": date.strftime("%Y-%m-%d"),
            "views": daily_views,
            "likes": int(daily_views * rate_likes),
            "coins": int(daily_views * rate_coins),
            "favorites": int(daily_views * rate_fav),
            "shares": int(daily_views * rate_share),
            "danmaku": int(daily_views * rate_danmaku),
            "comments": int(daily_views * rate_comment),
        })

# ============================================================
# 3. 粉丝画像表
# ============================================================
fans = []
for i in range(1, 2001):
    fans.append({
        "fan_id": i,
        "gender": random.choice(GENDERS),
        "age_group": random.choice(AGE_GROUPS),
        "city": random.choice(CITIES),
        "follow_time": (datetime.now() - timedelta(days=random.randint(0, 730))).strftime("%Y-%m-%d"),
    })

# ============================================================
# 4. 写入 SQLite
# ============================================================
import pandas as pd
conn = sqlite3.connect("bilibili_demo.db")
pd.DataFrame(videos).to_sql("videos", conn, index=False)
pd.DataFrame(video_stats).to_sql("video_stats", conn, index=False)
pd.DataFrame(fans).to_sql("fans", conn, index=False)
conn.close()

print(f"✅ 数据生成完毕：{len(videos)} 视频, {len(video_stats)} 条统计, {len(fans)} 粉丝")

# ============================================================
# 5. 语义模型定义
# ============================================================
dataset_config = {
    "datasets": [{
        "id": 1,
        "name": "B站视频数据",
        "table_name": "video_stats",
        "join_config": {
            "videos": "video_stats.video_id = videos.video_id",
            "fans": None,
        },
        "metrics": [
            {"id": 1, "biz_name": "views", "name": "views", "default_agg": "SUM",
             "alias": "播放量,播放数,观看量", "description": "视频播放总次数", "data_type": "NUMERIC"},
            {"id": 2, "biz_name": "likes", "name": "likes", "default_agg": "SUM",
             "alias": "点赞,点赞数,赞", "description": "点赞总数", "data_type": "NUMERIC"},
            {"id": 3, "biz_name": "coins", "name": "coins", "default_agg": "SUM",
             "alias": "投币,硬币,投币数,币", "description": "投币总数", "data_type": "NUMERIC"},
            {"id": 4, "biz_name": "favorites", "name": "favorites", "default_agg": "SUM",
             "alias": "收藏,收藏数", "description": "收藏总数", "data_type": "NUMERIC"},
            {"id": 5, "biz_name": "danmaku", "name": "danmaku", "default_agg": "SUM",
             "alias": "弹幕,弹幕数", "description": "弹幕总数", "data_type": "NUMERIC"},
            {"id": 6, "biz_name": "comments", "name": "comments", "default_agg": "SUM",
             "alias": "评论,评论数,留言", "description": "评论总数", "data_type": "NUMERIC"},
            {"id": 7, "biz_name": "shares", "name": "shares", "default_agg": "SUM",
             "alias": "分享,分享数,转发", "description": "分享总数", "data_type": "NUMERIC"},
            {"id": 8, "biz_name": "interaction_rate", "name": None, "default_agg": "AVG",
             "expression": "(likes + coins + favorites) * 1.0 / NULLIF(views, 0)",
             "alias": "互动率,交互率", "description": "互动率 = (点赞+投币+收藏)/播放量", "data_type": "NUMERIC"},
            {"id": 9, "biz_name": "coin_rate", "name": None, "default_agg": "AVG",
             "expression": "coins * 1.0 / NULLIF(views, 0)",
             "alias": "投币率,硬币率", "description": "投币率 = 投币数/播放量，B站核心质量指标", "data_type": "NUMERIC"},
            {"id": 10, "biz_name": "fan_count", "name": "fan_id", "default_agg": "COUNT",
             "alias": "粉丝数,粉丝量,关注数", "description": "粉丝总数", "data_type": "NUMERIC",
             "table": "fans"},
        ],
        "dimensions": [
            {"id": 20, "biz_name": "category", "name": "videos.category",
             "join_table": "videos", "join_key": "video_stats.video_id = videos.video_id",
             "alias": "分区,板块,类别,类型", "data_type": "CATEGORY"},
            {"id": 21, "biz_name": "stat_date", "name": "stat_date",
             "alias": "日期,时间,天,日", "data_type": "DATE"},
            {"id": 22, "biz_name": "video_title", "name": "videos.title",
             "join_table": "videos", "join_key": "video_stats.video_id = videos.video_id",
             "alias": "视频,稿件,内容", "data_type": "CATEGORY"},
            {"id": 23, "biz_name": "duration", "name": "videos.duration",
             "join_table": "videos", "join_key": "video_stats.video_id = videos.video_id",
             "alias": "时长,视频时长,长度", "data_type": "NUMERIC"},
            {"id": 24, "biz_name": "gender", "name": "gender",
             "alias": "性别,男女", "data_type": "CATEGORY", "table": "fans"},
            {"id": 25, "biz_name": "age_group", "name": "age_group",
             "alias": "年龄段,年龄,年龄分布", "data_type": "CATEGORY", "table": "fans"},
            {"id": 26, "biz_name": "city", "name": "city",
             "alias": "城市,地区,地域", "data_type": "CATEGORY", "table": "fans"},
        ],
        "terms": [
            {"id": 30, "name": "完播率", "alias": "播放完成率",
             "description": "平均播放时长/视频时长，B站衡量内容质量的核心指标"},
            {"id": 31, "name": "三连", "alias": "一键三连,点赞投币收藏",
             "description": "B站特色互动行为：同时点赞+投币+收藏"},
            {"id": 32, "name": "爆款", "alias": "热门,火",
             "description": "通常指播放量超过10万的视频"},
        ],
    }]
}

with open("dataset.yaml", "w", encoding="utf-8") as f:
    yaml.dump(dataset_config, f, allow_unicode=True, default_flow_style=False)
print("✅ dataset.yaml 已生成")

# ============================================================
# 6. Few-shot 示例
# ============================================================
exemplars = [
    {"question": "最近7天播放量趋势",
     "s2sql": "SELECT stat_date, SUM(views) FROM video_stats WHERE stat_date BETWEEN '{{-7d}}' AND '{{today}}' GROUP BY stat_date ORDER BY stat_date"},
    {"question": "各分区播放量排名",
     "s2sql": "SELECT category, SUM(views) FROM video_stats JOIN videos ON video_stats.video_id = videos.video_id GROUP BY category ORDER BY SUM(views) DESC"},
    {"question": "上个月点赞最多的5个视频",
     "s2sql": "SELECT video_title, SUM(likes) FROM video_stats JOIN videos ON video_stats.video_id = videos.video_id WHERE stat_date BETWEEN '{{last_month_start}}' AND '{{last_month_end}}' GROUP BY video_title ORDER BY SUM(likes) DESC LIMIT 5"},
    {"question": "最近7天互动率是多少",
     "s2sql": "SELECT AVG((likes + coins + favorites) * 1.0 / NULLIF(views, 0)) FROM video_stats WHERE stat_date BETWEEN '{{-7d}}' AND '{{today}}'"},
    {"question": "对比知识区和生活区的投币率",
     "s2sql": "SELECT category, AVG(coins * 1.0 / NULLIF(views, 0)) FROM video_stats JOIN videos ON video_stats.video_id = videos.video_id WHERE category IN ('知识', '生活') AND stat_date BETWEEN '{{-30d}}' AND '{{today}}' GROUP BY category"},
    {"question": "最近30天新增粉丝城市分布",
     "s2sql": "SELECT city, COUNT(*) FROM fans WHERE follow_time BETWEEN '{{-30d}}' AND '{{today}}' GROUP BY city ORDER BY COUNT(*) DESC"},
    {"question": "最近7天各分区弹幕数和评论数",
     "s2sql": "SELECT category, SUM(danmaku), SUM(comments) FROM video_stats JOIN videos ON video_stats.video_id = videos.video_id WHERE stat_date BETWEEN '{{-7d}}' AND '{{today}}' GROUP BY category"},
    {"question": "本周播放量和上周对比",
     "s2sql": "SELECT stat_date, SUM(views) FROM video_stats WHERE stat_date BETWEEN '{{this_week_start}}' AND '{{today}}' GROUP BY stat_date ORDER BY stat_date"},
    {"question": "深圳的粉丝有多少",
     "s2sql": "SELECT COUNT(*) FROM fans WHERE city = '深圳'"},
    {"question": "科技区播放量最高的3个视频",
     "s2sql": "SELECT video_title, SUM(views) FROM video_stats JOIN videos ON video_stats.video_id = videos.video_id WHERE category = '科技' GROUP BY video_title ORDER BY SUM(views) DESC LIMIT 3"},
    {"question": "最近7天播放量最高的5个视频",
     "s2sql": "SELECT video_title, SUM(views) FROM video_stats JOIN videos ON video_stats.video_id = videos.video_id WHERE stat_date BETWEEN '{{-7d}}' AND '{{today}}' GROUP BY video_title ORDER BY SUM(views) DESC LIMIT 5"},
    {"question": "各分区视频数量",
     "s2sql": "SELECT category, COUNT(DISTINCT video_stats.video_id) FROM video_stats JOIN videos ON video_stats.video_id = videos.video_id GROUP BY category"},
    {"question": "最近7天评论最多的视频",
     "s2sql": "SELECT video_title, SUM(comments) FROM video_stats JOIN videos ON video_stats.video_id = videos.video_id WHERE stat_date BETWEEN '{{-7d}}' AND '{{today}}' GROUP BY video_title ORDER BY SUM(comments) DESC LIMIT 10"},
    {"question": "粉丝男女比例",
     "s2sql": "SELECT gender, COUNT(*) FROM fans GROUP BY gender"},
    {"question": "各分区平均视频时长",
     "s2sql": "SELECT category, AVG(duration) FROM videos GROUP BY category"},
    {"question": "最近7天分享最多的视频",
     "s2sql": "SELECT video_title, SUM(shares) FROM video_stats JOIN videos ON video_stats.video_id = videos.video_id WHERE stat_date BETWEEN '{{-7d}}' AND '{{today}}' GROUP BY video_title ORDER BY SUM(shares) DESC LIMIT 5"},
]

with open("exemplars.json", "w", encoding="utf-8") as f:
    json.dump(exemplars, f, ensure_ascii=False, indent=2)
print(f"✅ exemplars.json 已生成（{len(exemplars)} 条）")
print("\n🎉 全部数据生成完毕！运行：streamlit run app.py")
